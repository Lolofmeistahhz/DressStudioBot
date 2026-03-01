"""
handlers/catalog.py

Картинки:
  Экран выбора цвета   → pt["color_palette_url"]  (палитра цветов типа)
  Экран выбора размера → pt["size_chart_url"]      (размерная сетка)
  Карточка товара      → product["image_url"]
"""
import asyncio
import logging
from aiogram import Router, F
from aiogram.types import Message, CallbackQuery

from handlers.utils import safe_answer, fetch_image, send_photo_or_text, to_text
from keyboards.catalog import (
    product_types_kb, colors_kb, sizes_kb,
    add_to_cart_kb, after_add_kb, cart_kb,
    confirm_order_kb, payment_kb,
)
from keyboards.main import main_menu
from services import api

router = Router()
logger = logging.getLogger(__name__)


def _size_table_text(sizes):
    has_waist = any(s.get("waist_width") for s in sizes)
    header = "Р-р  | Дл  | Шир" + (" | Пояс" if has_waist else "") + " | Рук | Пл"
    rows   = [header, "─" * len(header)]
    for s in sizes:
        avail = "✓" if s.get("_available") else "✗"
        row   = f"{s['label']:4} {avail}| {s.get('length','—'):3} | {s.get('width','—'):3}"
        if has_waist:
            row += f" | {s.get('waist_width','—'):4}"
        row += f" | {s.get('sleeve','—'):3} | {s.get('shoulders','—')}"
        rows.append(row)
    return "\n".join(rows)


@router.message(F.text == "🛍 Каталог")
async def show_catalog(message: Message):
    types = await api.get_product_types()
    if not types:
        await message.answer("😔 Каталог пока пуст.")
        return
    await message.answer("🛍 <b>Каталог</b>\n\nВыберите тип изделия:", reply_markup=product_types_kb(types))


@router.callback_query(F.data == "catalog:back")
async def cb_catalog_back(callback: CallbackQuery):
    await safe_answer(callback)
    await callback.message.delete()
    await callback.message.answer("Главное меню", reply_markup=main_menu)


@router.callback_query(F.data == "catalog:types")
async def cb_catalog_types(callback: CallbackQuery):
    await safe_answer(callback)
    types = await api.get_product_types()
    if not types:
        return
    await to_text(callback, "🛍 <b>Каталог</b>\n\nВыберите тип изделия:", product_types_kb(types))


# Тип → цвета: показываем color_palette_url
@router.callback_query(F.data.startswith("pt:"))
async def cb_product_type(callback: CallbackQuery):
    await safe_answer(callback)
    type_id = int(callback.data.split(":")[1])
    pt, colors = await asyncio.gather(
        api.get_product_type(type_id),
        api.get_type_colors(type_id),
    )
    if not pt:
        await callback.message.answer("❌ Тип изделия не найден")
        return
    if not colors:
        return
    text = (
        f"<b>{pt['name']}</b>\n"
        + (f"Состав: {pt['composition']}\n" if pt.get("composition") else "")
        + f"Цена: от <b>{pt['base_price']} ₽</b>\n\nВыберите цвет:"
    )
    await send_photo_or_text(callback, pt.get("color_palette_url"), text, colors_kb(colors, type_id))


# Цвет → размеры: показываем size_chart_url
@router.callback_query(F.data.startswith("color:"))
async def cb_color(callback: CallbackQuery):
    await safe_answer(callback)
    _, type_id_s, color_id_s = callback.data.split(":")
    type_id, color_id = int(type_id_s), int(color_id_s)

    pt, sizes, colors, products = await asyncio.gather(
        api.get_product_type(type_id),
        api.get_type_sizes(type_id),
        api.get_type_colors(type_id),
        api.get_ready_products(product_type_id=type_id, color_id=color_id),
    )
    if not pt or not sizes:
        return

    available_labels = {p["size_label"] for p in (products or []) if p["stock_quantity"] > 0}
    for s in sizes:
        s["_available"] = s["label"] in available_labels

    color_name = next(
        (c["color"]["name"] for c in (colors or []) if c["color"]["id"] == color_id), ""
    )
    stock_note = (
        "✓ — в наличии  ✗ — нет на складе"
        if available_labels
        else "⚠️ <b>Этот цвет сейчас отсутствует</b> — доступен кастомный заказ"
    )
    avail_str   = ", ".join(s["label"] for s in sizes if s.get("_available"))
    unavail_str = ", ".join(s["label"] for s in sizes if not s.get("_available"))
    kb = sizes_kb(sizes, type_id, color_id, available_labels)

    parts = [f"<b>{pt['name']}</b> · {color_name}"]
    if avail_str:
        parts.append(f"\n✅ В наличии: <b>{avail_str}</b>")
    if unavail_str:
        parts.append(f"❌ Нет: {unavail_str}")
    parts.append(f"\n{stock_note}\n\nВыберите размер:")
    caption = "\n".join(parts)

    size_chart_url = pt.get("size_chart_url")
    if size_chart_url:
        photo = await fetch_image(size_chart_url)
        if photo:
            try:
                await callback.message.delete()
            except Exception:
                pass
            await callback.message.answer_photo(photo=photo, caption=caption, reply_markup=kb)
            return

    # Нет картинки — текстовая таблица
    text = (
        f"<b>{pt['name']}</b> · {color_name}\n\n"
        f"<code>{_size_table_text(sizes)}</code>\n\n"
        f"{stock_note}\n\nВыберите размер:"
    )
    await to_text(callback, text, kb)


@router.callback_query(F.data.startswith("size_na:"))
async def cb_size_not_available(callback: CallbackQuery):
    size = callback.data.split(":")[1]
    await safe_answer(callback, f"Размер {size} сейчас отсутствует.\nОформите кастомный заказ 🧵", show_alert=True)


# Размер → карточка: показываем image_url товара
@router.callback_query(F.data.startswith("size:"))
async def cb_size(callback: CallbackQuery):
    await safe_answer(callback)
    _, type_id_s, color_id_s, size_label = callback.data.split(":")
    type_id, color_id = int(type_id_s), int(color_id_s)
    products, pt = await asyncio.gather(
        api.get_ready_products(product_type_id=type_id, color_id=color_id),
        api.get_product_type(type_id),
    )
    if not pt:
        return
    product    = next((p for p in (products or []) if p["size_label"] == size_label), None)
    color_name = product["color"]["name"] if product else ""
    if not product or product["stock_quantity"] == 0:
        return
    text = (
        f"<b>{pt['name']}</b>\n"
        f"Цвет: <b>{color_name}</b> · Размер: <b>{size_label}</b>\n"
        f"Цена: <b>{product['price']} ₽</b>\n"
        f"На складе: {product['stock_quantity']} шт.\n\nДобавить в корзину?"
    )
    await send_photo_or_text(callback, product.get("image_url"), text, add_to_cart_kb(product["id"], type_id, color_id))


@router.callback_query(F.data.startswith("cart_add:"))
async def cb_add_to_cart(callback: CallbackQuery):
    await safe_answer(callback)
    parts = callback.data.split(":")
    product_id, type_id, color_id = int(parts[1]), int(parts[2]), int(parts[3])
    user = await api.get_user(callback.from_user.id)
    if not user or not user.get("delivery_complete"):
        await callback.message.answer("⚠️ Сначала заполните данные доставки в разделе «Профиль»")
        return
    cart = await api.add_to_cart(callback.from_user.id, product_id)
    if not cart:
        await callback.message.answer("❌ Не удалось добавить в корзину")
        return
    text = (
        f"✅ <b>Добавлено в корзину!</b>\n\n"
        f"В корзине: {cart['items_count']} поз. на <b>{cart['total']} ₽</b>\n\nЧто дальше?"
    )
    kb = after_add_kb(type_id, color_id)
    if callback.message.photo:
        try:
            await callback.message.edit_caption(caption=text, reply_markup=kb)
        except Exception:
            await callback.message.answer(text, reply_markup=kb)
    else:
        try:
            await callback.message.edit_text(text, reply_markup=kb)
        except Exception:
            await callback.message.answer(text, reply_markup=kb)


def _cart_text(cart):
    lines = ["🛒 <b>Корзина</b>\n"]
    for item in cart["items"]:
        p = item["ready_product"]
        lines.append(
            f"• {p['product_type']['name']} {p['color']['name']} р.{p['size_label']}"
            f" × {item['quantity']} = <b>{item['subtotal']} ₽</b>"
        )
    lines.append(f"\n💰 Итого: <b>{cart['total']} ₽</b>")
    return "\n".join(lines)


@router.message(F.text == "🛒 Корзина")
async def show_cart(message: Message):
    cart = await api.get_cart(message.from_user.id)
    if not cart or not cart.get("items"):
        await message.answer("🛒 Корзина пуста", reply_markup=cart_kb(False))
        return
    await message.answer(_cart_text(cart), reply_markup=cart_kb(True))


@router.callback_query(F.data == "cart:view")
async def cb_cart_view(callback: CallbackQuery):
    await safe_answer(callback)
    cart = await api.get_cart(callback.from_user.id)
    has  = bool(cart and cart.get("items"))
    await to_text(callback, _cart_text(cart) if has else "🛒 Корзина пуста", cart_kb(has))


@router.callback_query(F.data.startswith("cart_qty:"))
async def cb_cart_qty(callback: CallbackQuery):
    await safe_answer(callback)
    _, item_id_s, delta_s = callback.data.split(":")
    item_id, delta = int(item_id_s), int(delta_s)
    cart = await api.get_cart(callback.from_user.id)
    if not cart:
        return
    item = next((i for i in cart["items"] if i["id"] == item_id), None)
    if not item:
        return
    new_qty = item["quantity"] + delta
    result  = (
        await api.remove_cart_item(callback.from_user.id, item_id)
        if new_qty <= 0
        else await api.update_cart_item(callback.from_user.id, item_id, new_qty)
    )
    if not result:
        return
    has = bool(result.get("items"))
    await to_text(callback, _cart_text(result) if has else "🛒 Корзина пуста", cart_kb(has))


@router.callback_query(F.data.startswith("cart_rm:"))
async def cb_cart_remove(callback: CallbackQuery):
    await safe_answer(callback, "Удалено")
    result = await api.remove_cart_item(callback.from_user.id, int(callback.data.split(":")[1]))
    if not result:
        return
    has = bool(result.get("items"))
    await to_text(callback, _cart_text(result) if has else "🛒 Корзина пуста", cart_kb(has))


@router.callback_query(F.data == "cart:clear")
async def cb_cart_clear(callback: CallbackQuery):
    await safe_answer(callback)
    await api.clear_cart(callback.from_user.id)
    await to_text(callback, "🛒 Корзина очищена", cart_kb(False))


@router.callback_query(F.data == "cart:checkout")
async def cb_checkout(callback: CallbackQuery):
    await safe_answer(callback)
    user = await api.get_user(callback.from_user.id)
    if not user or not user.get("delivery_complete"):
        await callback.message.answer("⚠️ Заполните данные доставки в профиле")
        return
    cart = await api.get_cart(callback.from_user.id)
    if not cart or not cart.get("items"):
        return
    carrier_map = {"cdek": "СДЭК", "yandex": "Яндекс Доставка"}
    text = (
        f"{_cart_text(cart)}\n\n<b>📦 Доставка:</b>\n"
        f"Получатель: {user['delivery_name']}\n"
        f"Телефон: {user['phone']}\n"
        f"Город: {user['delivery_city']}\n"
        f"Адрес: {user['delivery_address']}\n"
        f"Перевозчик: {carrier_map.get(user.get('delivery_carrier') or '', '—')}\n\n"
        f"Подтверждаете заказ?"
    )
    await to_text(callback, text, confirm_order_kb())


@router.callback_query(F.data == "order:confirm")
async def cb_order_confirm(callback: CallbackQuery):
    await safe_answer(callback)
    await to_text(callback, "⏳ Оформляем заказ...", None)
    order = await api.create_ready_order(callback.from_user.id)
    if not order:
        await callback.message.edit_text("❌ Не удалось создать заказ. Попробуйте позже.")
        return
    await callback.message.edit_text("⏳ Создаём ссылку на оплату...")
    payment = await api.create_payment("ready_order", order["id"], float(order["total_price"]))
    if not payment:
        await callback.message.edit_text(
            f"✅ Заказ <b>№{order['id']}</b> создан!\n"
            f"Сумма: <b>{order['total_price']} ₽</b>\n\n"
            f"⚠️ Не удалось создать ссылку. Зайдите в «Мои заказы».",
        )
        return
    await callback.message.edit_text(
        f"✅ Заказ <b>№{order['id']}</b> создан!\n"
        f"Сумма: <b>{order['total_price']} ₽</b>\n\nНажмите кнопку для оплаты:",
        reply_markup=payment_kb(payment["confirmation_url"]),
    )