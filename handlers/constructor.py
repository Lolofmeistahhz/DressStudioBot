"""
handlers/constructor.py

Открывает WebApp конструктора мерча и принимает данные от него.
"""
import json
import logging

from aiogram import Router, F
from aiogram.types import Message, InlineKeyboardMarkup, InlineKeyboardButton, WebAppInfo

from config import settings
from services import api

logger = logging.getLogger(__name__)
router = Router()


def constructor_kb() -> InlineKeyboardMarkup:
    """Кнопка открытия WebApp."""
    return InlineKeyboardMarkup(inline_keyboard=[[
        InlineKeyboardButton(
            text="🎨 Открыть конструктор",
            web_app=WebAppInfo(url=settings.WEBAPP_URL),
        )
    ]])


@router.message(F.text == "🎨 Свой дизайн")
async def open_constructor(message: Message):
    """Кнопка в главном меню → открываем WebApp."""
    await message.answer(
        "🎨 <b>Конструктор мерча</b>\n\n"
        "Создайте изделие с вашим принтом:\n"
        "• Выберите тип и цвет изделия\n"
        "• Добавьте готовый принт или загрузите свой\n"
        "• Напишите текст любым шрифтом\n\n"
        "После отправки мастер свяжется с вами для уточнения деталей.",
        reply_markup=constructor_kb(),
    )


@router.message(F.web_app_data)
async def handle_webapp_data(message: Message):
    """
    Telegram вызывает этот хендлер когда WebApp вызывает tg.sendData().
    Получаем данные конструктора и создаём заявку на кастомный мерч.
    """
    try:
        data = json.loads(message.web_app_data.data)
    except json.JSONDecodeError:
        logger.error(f"Некорректные данные от WebApp: {message.web_app_data.data}")
        await message.answer("❌ Ошибка при получении данных. Попробуйте ещё раз.")
        return

    item_name  = data.get("item_name", "—")
    item_color = data.get("item_color", "—")
    size       = data.get("size", "—")
    base_price = data.get("base_price", 0)
    preview_b64 = data.get("preview_base64", "")

    # Отправляем превью клиенту
    if preview_b64 and preview_b64.startswith("data:image"):
        import base64, io
        from aiogram.types import BufferedInputFile
        img_data = base64.b64decode(preview_b64.split(",")[1])
        photo = BufferedInputFile(img_data, filename="preview.png")
        await message.answer_photo(
            photo=photo,
            caption=(
                f"✅ <b>Заявка на кастомный мерч принята!</b>\n\n"
                f"<b>Изделие:</b> {item_name} ({item_color})\n"
                f"<b>Размер:</b> {size}\n"
                f"<b>Базовая стоимость:</b> {base_price:,} ₽\n"
                f"<b>Стоимость печати:</b> уточняется мастером\n\n"
                f"Мы свяжемся с вами в ближайшее время для подтверждения деталей и итоговой стоимости 🧵"
            ),
        )
    else:
        await message.answer(
            f"✅ <b>Заявка на кастомный мерч принята!</b>\n\n"
            f"<b>Изделие:</b> {item_name} ({item_color})\n"
            f"<b>Размер:</b> {size}\n"
            f"<b>Базовая стоимость:</b> {base_price:,} ₽\n\n"
            f"Мы свяжемся с вами для уточнения деталей 🧵"
        )

    # TODO: когда появится модель CustomOrder — сохранять в БД через api.create_custom_order()
    logger.info(
        f"Кастомный заказ от {message.from_user.id}: "
        f"{item_name} {item_color} р.{size}"
    )