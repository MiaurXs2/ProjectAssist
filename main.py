from aiogram import types
import asyncio
import environs
from aiogram import Bot, Dispatcher, F
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup, CallbackQuery, message_id
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
import init_db
from models import SessionLocal, User, Role

env = environs.Env()
env.read_env()
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
        chat_id=admin_id,
        message_id=message_id,
        text="✅ Успешно, вы отказали в регистрации"
    )
    await bot.send_message(user_id,"❌ Вам отказано в регистрации")

async def main():
    await dp.start_polling(bot)

if __name__ == '__main__':
    asyncio.run(main())