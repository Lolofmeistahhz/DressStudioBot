"""
handlers/orders.py

«Мои заказы» — история заказов готового мерча и кастомных заявок.
"""
from aiogram import Router, F
from aiogram.types import Message, CallbackQuery

from keyboards.orders import (
    orders_menu_kb, orders_back_kb, order_pay_kb,
    READY_STATUS, CUSTOM_STATUS,
)
from services import api

router = Router()


@router.message(F.text == "📋 Мои заказы")
async def show_orders_menu(message: Message):
    await message.answer("📋 <b>Мои заказы</b>\n\nЧто показать?", reply_markup=orders_menu_kb())


@router.callback_query(F.data == "orders:menu")
async def cb_orders_menu(callback: CallbackQuery):
    await callback.message.edit_text(
        "📋 <b>Мои заказы</b>\n\nЧто показать?",
        reply_markup=orders_menu_kb(),
    )
    await callback.answer()


# ── Заказы мерча ──────────────────────────────────────────────────────────────

@router.callback_query(F.data == "orders:ready")
async def cb_ready_orders(callback: CallbackQuery):
    orders = await api.get_my_ready_orders(callback.from_user.id)

    if not orders:
        await callback.message.edit_text(
            "📭 Заказов мерча пока нет.",
            reply_markup=orders_back_kb(),
        )
        await callback.answer()
        return

    lines = ["🛍 <b>Заказы мерча:</b>\n"]
    for o in orders:
        status = READY_STATUS.get(o["status"], o["status"])
        tracking = f"\n   🔎 Трек: <code>{o['tracking_number']}</code>" if o.get("tracking_number") else ""
        lines.append(
            f"<b>№{o['id']}</b> — {status}\n"
            f"   💰 {o['total_price']} ₽ · {o['carrier'].upper()}{tracking}"
        )

    await callback.message.edit_text(
        "\n\n".join(lines),
        reply_markup=orders_back_kb(),
    )
    await callback.answer()


# ── Кастомные заказы ──────────────────────────────────────────────────────────

@router.callback_query(F.data == "orders:custom")
async def cb_custom_orders(callback: CallbackQuery):
    orders = await api.get_my_custom_orders(callback.from_user.id)

    if not orders:
        await callback.message.edit_text(
            "📭 Кастомных заказов пока нет.",
            reply_markup=orders_back_kb(),
        )
        await callback.answer()
        return

    lines = ["🧵 <b>Кастомные заказы:</b>\n"]
    for o in orders:
        status = CUSTOM_STATUS.get(o["status"], o["status"])
        price_line = ""
        if o.get("final_price"):
            price_line = f"\n   💰 {o['final_price']} ₽"
        elif o.get("recommended_price"):
            price_line = f"\n   💰 ~{o['recommended_price']} ₽ (ориент.)"

        lines.append(
            f"<b>№{o['id']}</b> — {status}\n"
            f"   р.{o['size_label']}{price_line}"
        )

    await callback.message.edit_text(
        "\n\n".join(lines),
        reply_markup=orders_back_kb(),
    )
    await callback.answer()