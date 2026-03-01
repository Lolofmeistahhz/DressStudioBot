from aiogram.types import ReplyKeyboardMarkup, KeyboardButton

main_menu = ReplyKeyboardMarkup(
    keyboard=[
        [KeyboardButton(text="🛍 Каталог"),      KeyboardButton(text="🧵 Кастомный заказ")],
        [KeyboardButton(text="🛒 Корзина"),       KeyboardButton(text="📋 Мои заказы")],
        [KeyboardButton(text="👤 Профиль")],
    ],
    resize_keyboard=True,
)