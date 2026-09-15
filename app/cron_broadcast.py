
import asyncio
from aiogram import Bot
from aiogram.enums import ParseMode
from sqlalchemy import select
from .config import settings
from .db import init_db, Session, User
from .i18n import t

async def run():
    await init_db()
    bot=Bot(settings.bot_token)
    async with Session() as s:
        users=(await s.scalars(select(User).where(User.registered==True,User.blocked==False,~User.tg_id.in_(settings.admins)))).all()
    for u in users:
        try:
            await bot.send_message(u.tg_id,
                "🤖✨ Botimiz faol ishlamoqda!\n\n"
                "Xizmatlardan foydalanish uchun botga qayting.\n"
                "Boshlash uchun /start bosing.")
        except Exception:
            async with Session.begin() as s:
                x=await s.scalar(select(User).where(User.tg_id==u.tg_id))
                # Do not immediately block: Telegram can temporarily reject messages.
                # Permanent blocks can be handled by admin/status errors later.
                pass
        await asyncio.sleep(.05)
    await bot.session.close()

if __name__=="__main__":
    asyncio.run(run())
