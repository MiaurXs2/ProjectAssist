from aiogram import types
import asyncio
import environs
from aiogram import Bot, Dispatcher, F
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup, CallbackQuery
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
import init_db

env = environs.Env()
env.read_env()
Token = env.str("TOKEN")

bot = Bot(token=Token)
dp = Dispatcher()
init_db.init_db()

class StatesGroup(StatesGroup):
    waiting_for_gitlab = State()
    gitlab = State("gitlab")

@dp.message(Command("start"))
async def start(message: types.Message):
    await message.answer("Зарегистрируйтесь: ", reply_markup=InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="Зарегестрироваться", callback_data="Register_user")]
    ]))

#                 Register
#___________________________________________________
@dp.callback_query(F.data == "Register_user")
async def response_for_gitlab(callback: CallbackQuery, state: FSMContext):
    await callback.message.edit_text("Введите свой gitlab: ")
    await state.set_state(StatesGroup.waiting_for_gitlab)

@dp.message(StatesGroup.waiting_for_gitlab)
async def get_a_gitlab(message: types.Message, state: FSMContext):
    gitlab = message.text
    await state.update_data(gitlab=gitlab)

async def main():
    await dp.start_polling(bot)

if __name__ == '__main__':
    asyncio.run(main())