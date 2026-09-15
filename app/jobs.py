import asyncio
from datetime import timedelta
from sqlalchemy import select
from aiogram.exceptions import TelegramForbiddenError
from .db import Session, MandatoryTarget, Order, User, DailyBroadcast, now
from .locksmm import status as api_status
from .config import settings

async def expire_channels(bot):
    expired=[]
    async with Session.begin() as s:
        xs=(await s.scalars(select(MandatoryTarget).where(MandatoryTarget.active==True))).all()
        for x in xs:
            if x.expires_at and x.expires_at<=now():
                x.active=False; expired.append((x.title,x.chat_id))
    for title,cid in expired:
        for aid in settings.admins:
            try: await bot.send_message(aid,f"⏰ Majburiy obuna muddati tugadi va o‘chirildi:\n📢 {title}\n🆔 {cid}")
            except Exception: pass

async def sync_smm_orders():
    async with Session() as s:
        os=(await s.scalars(select(Order).where(Order.kind=="smm",Order.status=="processing",Order.provider_order_id.is_not(None)).limit(100))).all()
    if not os: return
    try: data=await api_status(orders=",".join(o.provider_order_id for o in os))
    except Exception: return
    async with Session.begin() as s:
        for o in os:
            item=data.get(o.provider_order_id) if isinstance(data,dict) else None
            raw=(item.get("status","") if isinstance(item,dict) else str(item)).lower()
            st="done" if "complete" in raw else "cancelled" if ("cancel" in raw or "fail" in raw) else "processing"
            x=await s.get(Order,o.id,with_for_update=True)
            if x and x.status=="processing": x.status=st

async def daily_broadcast_once(bot):
    async with Session() as s:
        users=(await s.scalars(select(User).where(User.registered==True,User.blocked==False))).all()
    for u in users:
        if u.tg_id in settings.admins: continue
        send=False
        async with Session.begin() as s:
            row=await s.scalar(select(DailyBroadcast).where(DailyBroadcast.user_tg_id==u.tg_id).with_for_update())
            current=now()
            if not row:
                row=DailyBroadcast(user_tg_id=u.tg_id,last_sent_at=current); s.add(row)
                continue
            if not row.last_sent_at or current-row.last_sent_at>=timedelta(hours=24): row.last_sent_at=current; send=True
        if send:
            try: await bot.send_message(u.tg_id,"🤖✨ Botimiz faol ishlamoqda!\n\nXizmatlardan foydalanish uchun /start bosing.")
            except TelegramForbiddenError:
                async with Session.begin() as s:
                    x=await s.scalar(select(User).where(User.tg_id==u.tg_id))
                    if x: x.blocked=True
            except Exception: pass
            await asyncio.sleep(.05)

async def maintenance_loop(bot):
    while True:
        try:
            await expire_channels(bot)
            await sync_smm_orders()
            await daily_broadcast_once(bot)
        except Exception: pass
        await asyncio.sleep(60)
