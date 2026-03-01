"""
handlers/start.py

/start — регистрируем пользователя, показываем меню.
Если данные доставки не заполнены — показываем предупреждение.
"""
from aiogram import Router, F
from aiogram.filters import CommandStart
from aiogram.types import Message

from keyboards.main import main_menu
from keyboards.profile import phone_request_kb
from services import api

router = Router()


@router.message(CommandStart())
async def cmd_start(message: Message):
    user = await api.upsert_user(
        telegram_id=message.from_user.id,
        username=message.from_user.username,
        full_name=message.from_user.full_name,
    )
    if not user:
        await message.answer("⚠️ Не удалось подключиться к серверу. Попробуйте позже.")
        return

    name = message.from_user.first_name or "друг"

    if not user.get("phone"):
        await message.answer(
            f"Привет, {name}! 👋\n\n"
            f"Добро пожаловать в <b>Lembro</b> — студию вышивки.\n\n"
            f"Для начала поделитесь номером телефона:",
            reply_markup=phone_request_kb(),
        )
        return

    delivery_ok = user.get("delivery_complete", False)
    extra = "" if delivery_ok else "\n\n⚠️ Не забудьте заполнить <b>данные доставки</b> в профиле — без них заказ оформить нельзя."

    await message.answer(
        f"С возвращением, {name}! 👋{extra}",
        reply_markup=main_menu,
    )


@router.message(F.contact)
async def handle_contact(message: Message):
    """Пользователь поделился контактом."""
    phone = message.contact.phone_number
    await api.set_phone(message.from_user.id, phone)
    name = message.from_user.first_name or "друг"
    await message.answer(
        f"Отлично, {name}! Номер сохранён ✅\n\n"
        f"⚠️ Не забудьте заполнить <b>данные доставки</b> в разделе «Профиль» — без них нельзя оформить заказ.",
        reply_markup=main_menu,
    )