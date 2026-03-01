from aiogram.types import (
    InlineKeyboardMarkup, InlineKeyboardButton,
    ReplyKeyboardMarkup, KeyboardButton,
)


def profile_kb(delivery_complete: bool) -> InlineKeyboardMarkup:
    buttons = []
    if not delivery_complete:
        buttons.append([InlineKeyboardButton(
            text="⚠️ Заполните данные доставки",
            callback_data="profile:delivery",
        )])
    buttons += [
        [InlineKeyboardButton(text="📱 Изменить телефон",  callback_data="profile:phone")],
        [InlineKeyboardButton(text="📦 Данные доставки",   callback_data="profile:delivery")],
    ]
    return InlineKeyboardMarkup(inline_keyboard=buttons)


def delivery_kb() -> InlineKeyboardMarkup:
    """Телефон здесь не нужен — он один и меняется через профиль."""
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="✏️ Имя получателя",  callback_data="dlv:name")],
        [InlineKeyboardButton(text="🏙 Город",            callback_data="dlv:city")],
        [InlineKeyboardButton(text="🏠 Адрес / ПВЗ",     callback_data="dlv:address")],
        [InlineKeyboardButton(text="🚚 Перевозчик",       callback_data="dlv:carrier")],
        [InlineKeyboardButton(text="◀️ Назад",            callback_data="profile:back")],
    ])


def carrier_kb() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="📦 СДЭК",              callback_data="carrier:cdek")],
        [InlineKeyboardButton(text="🚀 Яндекс Доставка",   callback_data="carrier:yandex")],
        [InlineKeyboardButton(text="◀️ Назад",              callback_data="profile:delivery")],
    ])


def phone_request_kb() -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(
        keyboard=[[KeyboardButton(text="📱 Поделиться номером", request_contact=True)]],
        resize_keyboard=True,
        one_time_keyboard=True,
    )