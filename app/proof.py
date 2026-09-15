from aiogram import Bot
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from sqlalchemy import select
from .config import settings
from .db import Session, Order

async def post_order(bot: Bot, order: Order):
    if not settings.proof_channel_id:
        return None
    text = ("🆕 <b>Yangi buyurtma</b>\n\n"
            f"🆔 Buyurtma: <code>#{order.id}</code>\n"
            f"👤 Mijoz ID: <code>{order.user_tg_id}</code>\n"
            f"📦 Turi: <b>{order.kind}</b>\n"
            f"🔢 Miqdor: {order.quantity or order.duration_months or '-'}\n"
            f"💰 Summa: <b>{order.price:,} so‘m</b>")
    kb = InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="📊 Holatni ko‘rish", callback_data=f"order_status:{order.id}")]])
    msg = await bot.send_message(settings.proof_channel_id, text, reply_markup=kb, parse_mode="HTML")
    async with Session.begin() as s:
        o = await s.get(Order, order.id)
        if o:
            o.proof_message_id = msg.message_id
    return msg
