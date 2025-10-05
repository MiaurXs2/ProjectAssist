from aiogram import types
import asyncio
import environs
from aiogram import Bot, Dispatcher, F
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup, CallbackQuery, message_id, Message
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
import init_db
from sqlalchemy import delete
from models import SessionLocal, User, Role, user_roles, developer_reviewer

env = environs.Env()
env.read_env("example.env")
Token = env.str("TOKEN")
admin_id = env.int("ADMIN_ID")
session = SessionLocal()

bot = Bot(token=Token)
dp = Dispatcher()
init_db.init_db()

class StatesGroup(StatesGroup):
    waiting_for_gitlab = State()
    choosing_roles = State()

@dp.message(Command("start"))
async def start(message: types.Message, state: FSMContext):
    user_id = message.from_user.id
    await state.update_data(user_id=user_id)
    await message.answer("🔑 Зарегистрируйтесь: ", reply_markup=InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🔐 Зарегестрироваться", callback_data="Register_user")]
    ]))

#                 Register & Admin solution
#___________________________________________________
@dp.callback_query(F.data == "Register_user")
async def request_for_gitlab(callback: CallbackQuery, state: FSMContext):
    user_id = callback.from_user.id
    RegisterCheck = session.query(User).filter(User.tg_id == user_id).first()
    if RegisterCheck is None:
        await callback.message.edit_text("⌨️ Введите свой gitlab: ")
        await state.set_state(StatesGroup.waiting_for_gitlab)
        await callback.answer()
    else:
        await callback.answer(
            "❌ Вы уже зарегистрированы.\n\n⚠️ Для повторной регистрации обратитесь к администратору.",
            show_alert=True
        )

@dp.message(StatesGroup.waiting_for_gitlab)
async def response_a_gitlab(message: types.Message, state: FSMContext):
    gitlab = message.text
    await state.update_data(gitlab=gitlab, selected_roles=[])

    roles = session.query(Role).all()
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        *[[InlineKeyboardButton(text=role.role, callback_data=f"toggle_role_{role.id}")] for role in roles]
    ])

    await message.answer("✏️ Выберите одну или несколько ролей:", reply_markup=keyboard)
    await state.set_state(StatesGroup.choosing_roles)

async def get_roles_keyboard(roles, selected_roles):
    keyboard = InlineKeyboardMarkup(inline_keyboard=[])
    for role in roles:
        is_selected = role.id in selected_roles
        text = f"✅ {role.role}" if is_selected else role.role
        keyboard.inline_keyboard.append([
            InlineKeyboardButton(
                text=text,
                callback_data=f"toggle_role_{role.id}"
            )
        ])

    keyboard.inline_keyboard.append([
        InlineKeyboardButton(
            text="✅ Подтвердить",
            callback_data="roles_done"
        )])
    return keyboard

@dp.callback_query(F.data.startswith("toggle_role_"))
async def toggle_role(callback: CallbackQuery, state: FSMContext):
    role_id = int(callback.data.split("_")[-1])
    data = await state.get_data()
    selected_roles = data.get("selected_roles", [])

    if role_id in selected_roles:
        selected_roles.remove(role_id)
    else:
        selected_roles.append(role_id)

    await state.update_data(selected_roles=selected_roles)

    # Получаем список всех ролей из базы
    roles = session.query(Role).all()

    # Обновляем клавиатуру с галочками
    keyboard = await get_roles_keyboard(roles, selected_roles)
    await callback.message.edit_reply_markup(reply_markup=keyboard)
    await callback.answer()

@dp.callback_query(F.data == "roles_done")
async def roles_done(callback: CallbackQuery, state: FSMContext):
    data = await state.get_data()
    gitlab = data["gitlab"]
    user_id = callback.from_user.id
    selected_roles = data.get("selected_roles", [])

    if not selected_roles:
        await callback.answer("❗ Выберите хотя бы одну роль!", show_alert=True)
        return

    # Соберем названия ролей
    roles = session.query(Role).filter(Role.id.in_(selected_roles)).all()
    role_names = ', '.join([r.role for r in roles])

    await callback.message.edit_text("✅ Запрос на регистрацию отправлен")

    await bot.send_message(admin_id, f"❓ Запрос на регистрацию\n"
                                     f"👤 Gitlab: {gitlab}\n"
                                     f"🪪 Роли: {role_names}",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="✅ Одобрить", callback_data=f"Register_accept_{user_id}_{gitlab}_{'-'.join(map(str, selected_roles))}")],
            [InlineKeyboardButton(text="❌ Отклонить", callback_data=f"Register_decline_{user_id}")],
        ]))

@dp.callback_query(F.data.startswith("Register_accept_"))
async def register_user_accept(callback: CallbackQuery):
    _, _, user_id, gitlab, role_ids_str = callback.data.split("_", 4)
    user_id = int(user_id)
    role_ids = list(map(int, role_ids_str.split("-")))

    session.rollback()

    # Проверяем, есть ли уже такой пользователь
    user = session.query(User).filter_by(tg_id=user_id).first()
    if not user:
        user = User(tg_id=user_id, gitlab=gitlab)
        session.add(user)
        session.commit()

    roles = session.query(Role).filter(Role.id.in_(role_ids)).all()

    for role in roles:
        if role not in user.roles:
            user.roles.append(role)

    session.commit()

    await callback.message.edit_text("✅ Успешно, вы подтвердили регистрацию")
    await bot.send_message(user_id, "✅ Регистрация одобрена")

@dp.callback_query(F.data.startswith("Register_decline_"))
async def register_user_decline(callback: CallbackQuery, state: FSMContext):
    user_id = callback.data.split("_")[2]
    message_id = callback.message.message_id
    await bot.edit_message_text(
        chat_id=callback.from_user.id,
        message_id=message_id,
        text="✅ Успешно, вы отказали в регистрации"
    )
    await bot.send_message(user_id,"❌ Вам отказано в регистрации")

#                  Admin's menu
#----------------------------------------------------------
@dp.message(Command("m"))
async def Admin_menu(message: Message, tg_id=None):
    if admin_id == message.from_user.id or admin_id == tg_id:
        try:
            await message.edit_text("✏️ Панель админа: ",
            reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="🗑️ Удалить пользователя", callback_data="Delete_user")],
                [InlineKeyboardButton(text="📝 Назначить reviewer(а)", callback_data="Admin_set_reviewer")]
            ]))
        except:
            await message.answer(text="✏️ Панель админа: ",
                                          reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="🗑️ Удалить пользователя", callback_data="Delete_user")],
            [InlineKeyboardButton(text="📝 Назначить reviewer(а)", callback_data="Admin_set_reviewer")]
            ]))
    else:
        await message.answer("🤔 Как вы вообще узнали про эту команду?")

@dp.callback_query(F.data == "Delete_user")
async def Admin_delete_user_select(callback: CallbackQuery, state: FSMContext):
    users = session.query(User).all()
    keyboard = InlineKeyboardMarkup(inline_keyboard=[])
    for gitlab in users:
        keyboard.inline_keyboard.append([
            InlineKeyboardButton(
                text=str(gitlab.gitlab),
                callback_data=f"Delete_user_{gitlab.gitlab}")
        ])
    keyboard.inline_keyboard.append([
        InlineKeyboardButton(
            text="← Назад",
            callback_data=f"Back_to_admin_menu")
    ])
    try:
        await bot.edit_message_text("📋 Список пользователей:", reply_markup=keyboard,
                                    chat_id=callback.from_user.id, message_id=callback.message.message_id)
    except:
        await callback.message.answer("📋 Список пользователей:", reply_markup=keyboard)
    await callback.answer()

@dp.callback_query(F.data.startswith("Delete_user_"))
async def Admin_delete_user(callback: CallbackQuery, state: FSMContext):
    gitlab = callback.data.split("_")[2]
    try:
        session.query(User).filter(User.gitlab == gitlab).delete()
        session.execute(
            delete(developer_reviewer).where(
                (gitlab == developer_reviewer.c.developer) |
                (gitlab == developer_reviewer.c.reviewer)
            ))
        session.execute(
            delete(user_roles).where(gitlab == user_roles.c.gitlab)
        )
        session.commit()
        message_id = callback.message.message_id
        await bot.edit_message_text("✅ Успешно", reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="← Назад", callback_data="Delete_user")]
        ]), chat_id=callback.from_user.id, message_id=message_id)
    except:
        await callback.answer("⚠️ Ошибка")
    await callback.answer()

@dp.callback_query(F.data == "Admin_set_reviewer")
async def Admin_select_developer(callback: CallbackQuery, state: FSMContext):
    users = (
        session.query(User)
        .join(user_roles, user_roles.c.gitlab == User.gitlab)
        .join(Role, Role.role == user_roles.c.role)
        .filter(Role.role == "разработчик")
    )
    keyboard = InlineKeyboardMarkup(inline_keyboard=[])
    for gitlab in users:
        keyboard.inline_keyboard.append([
            InlineKeyboardButton(
                text=str(gitlab.gitlab),
                callback_data=f"Developer_is_{gitlab.gitlab}")
        ])
    keyboard.inline_keyboard.append([
        InlineKeyboardButton(
            text="← Назад",
            callback_data=f"Back_to_admin_menu")
    ])
    try:
        await bot.edit_message_text("👤 Выберите кому назначить reviewer(a)", reply_markup=keyboard,
                                    chat_id=callback.from_user.id, message_id=callback.message.message_id)
    except:
        await callback.message.answer("👤 Выберите кому назначить reviewer(a)", reply_markup=keyboard)
    await callback.answer()

@dp.callback_query(F.data.startswith("Developer_is_"))
async def Admin_select_reviewer(callback: CallbackQuery, state: FSMContext):
    developer = callback.data.split("_")[2]
    users = (
        session.query(User)
        .join(user_roles, user_roles.c.gitlab == User.gitlab)
        .join(Role, Role.role == user_roles.c.role)
        .filter(Role.role == "разработчик")
    )
    keyboard = InlineKeyboardMarkup(inline_keyboard=[])
    for gitlab in users:
        if gitlab.gitlab == developer:
            pass
        else:
            keyboard.inline_keyboard.append([
                InlineKeyboardButton(
                    text=str(gitlab.gitlab),
                    callback_data=f"ReviewerIs_{gitlab.gitlab}_DeveloperIs_{developer}")
            ])
    keyboard.inline_keyboard.append([
        InlineKeyboardButton(
            text="← Назад",
            callback_data=f"Back_to_admin_menu")
    ])
    try:
        await bot.edit_message_text("👤 Выберите кто будет reviewer(ом):", reply_markup=keyboard,
                                    chat_id=callback.from_user.id, message_id=callback.message.message_id)
    except:
        await callback.message.answer("👤 Выберите кто будет reviewer(ом):", reply_markup=keyboard)
    await callback.answer()

@dp.callback_query(F.data.startswith("ReviewerIs_"))
async def Developer_Reviewer_set(callback: CallbackQuery, state: FSMContext):
    reviewer_gitlab = callback.data.split("_")[1]
    developer_gitlab = callback.data.split("_")[3]

    reviewer = session.query(User).filter_by(gitlab=reviewer_gitlab).first()
    developer = session.query(User).filter_by(gitlab=developer_gitlab).first()

    check = session.execute(
        developer_reviewer.select().where(
            (developer_reviewer.c.developer == developer_gitlab) &
            (developer_reviewer.c.reviewer == reviewer_gitlab)
        )
    ).first()

    if check is None:
        developer.reviewers.append(reviewer)
        session.add(developer)
        session.commit()
        try:
            await bot.edit_message_text(f"👨🏻‍💻 Разработчик: {developer.gitlab}\n\n"
                                        f"👀 Reviewer: {reviewer.gitlab}\n\n"
                                        f"✅ Успешно добавлены", reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="← Назад", callback_data=f"Admin_set_reviewer")]
        ]), chat_id=callback.from_user.id, message_id=callback.message.message_id)
        except:
            await callback.message.answer("⚠️ Уже был добавлен")
    else:
        try:
            await bot.edit_message_text("⚠️ Уже был добавлен", reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="← Назад", callback_data=f"Admin_set_reviewer")]
        ]), chat_id=callback.from_user.id, message_id=callback.message.message_id)
        except:
            await callback.message.answer("⚠️ Уже был добавлен")

    await callback.answer()

@dp.callback_query(F.data == "Back_to_admin_menu")
async def Back_to_admin_menu(callback: CallbackQuery):
    tg_id = admin_id
    await Admin_menu(callback.message, tg_id)
    await callback.answer()

async def main():
    await dp.start_polling(bot)

if __name__ == '__main__':
    asyncio.run(main())