"""
handlers/utils.py
"""
import logging
import httpx
from aiogram.types import CallbackQuery, BufferedInputFile

logger = logging.getLogger(__name__)


async def safe_answer(callback: CallbackQuery, text: str = "", show_alert: bool = False):
    """callback.answer() в try/except — Telegram даёт только ~10 сек."""
    try:
        await callback.answer(text, show_alert=show_alert)
    except Exception:
        pass


async def fetch_image(url: str | None) -> BufferedInputFile | None:
    if not url:
        return None
    try:
        async with httpx.AsyncClient(timeout=10) as c:
            r = await c.get(url)
            if not r.is_success:
                logger.warning(f"Image {url} → {r.status_code}")
                return None
            if "image" not in r.headers.get("content-type", ""):
                logger.warning(f"Image {url} wrong content-type")
                return None
            return BufferedInputFile(r.content, filename=url.split("/")[-1] or "img.jpg")
    except Exception as e:
        logger.warning(f"Image fetch error {url}: {e}")
        return None


async def send_photo_or_text(callback: CallbackQuery, photo_url, text, reply_markup):
    photo = await fetch_image(photo_url)
    if photo:
        try:
            await callback.message.delete()
        except Exception:
            pass
        await callback.message.answer_photo(photo=photo, caption=text, reply_markup=reply_markup)
    else:
        await to_text(callback, text, reply_markup)


async def to_text(callback: CallbackQuery, text: str, reply_markup):
    if callback.message.photo:
        try:
            await callback.message.delete()
        except Exception:
            pass
        await callback.message.answer(text, reply_markup=reply_markup)
    else:
        try:
            await callback.message.edit_text(text, reply_markup=reply_markup)
        except Exception:
            await callback.message.answer(text, reply_markup=reply_markup)