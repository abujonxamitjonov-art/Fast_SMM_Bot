import asyncio
import os
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request, HTTPException
from fastapi.responses import JSONResponse
from aiogram import Bot, Dispatcher
from aiogram.types import Update, BotCommand, BotCommandScopeChat

from .config import settings
from .db import init_db
from .catalog import seed_catalog, sync_services
from .handlers.user import router as user_router
from .handlers.admin import router as admin_router
from .jobs import maintenance_loop


bot = Bot(settings.bot_token)

dp = Dispatcher()
dp.include_router(user_router)
dp.include_router(admin_router)

maintenance_task = None


async def set_commands():
    await bot.set_my_commands([
        BotCommand(
            command="start",
            description="Botni boshlash"
        )
    ])

    admin_cmds = [
        ("foydalanuvchilar", "Foydalanuvchilar"),
        ("foydalanuvchi", "Foydalanuvchi"),
        ("bloklash", "Bloklash"),
        ("blokdan_chiqarish", "Blokdan chiqarish"),
        ("reklama", "Tarqatma"),
        ("xabar", "Xabar yuborish"),
        ("balans", "Balans"),
        ("balans_qoshish", "Balans qo‘shish"),
        ("balans_ayirish", "Balans ayirish"),
        ("tolovlar", "To‘lovlar"),
        ("tolov", "To‘lov"),
        ("buyurtmalar", "Buyurtmalar"),
        ("buyurtma", "Buyurtma"),
        ("buyurtma_holati", "Buyurtma holati"),
        ("xizmatlar", "Xizmatlar"),
        ("xizmat", "Xizmat"),
        ("ustama", "Ustama"),
        ("xizmatlarni_yangilash", "Xizmatlarni yangilash"),
        ("api_holati", "API holati"),
        ("kanallar", "Majburiy obunalar"),
        ("kanal_qoshish", "Kanal qo‘shish"),
        ("kanal_ochirish", "Kanal o‘chirish"),
        ("minimal_tolov", "Minimal to‘lov"),
        ("sozlamalar", "Sozlamalar"),
    ]

    for aid in settings.admins:
        try:
            await bot.set_my_commands(
                [
                    BotCommand(command=c, description=d)
                    for c, d in admin_cmds
                ],
                scope=BotCommandScopeChat(chat_id=aid),
            )
        except Exception:
            pass


@asynccontextmanager
async def lifespan(app: FastAPI):
    global maintenance_task

    await init_db()

    await seed_catalog()

    try:
        await sync_services()
    except Exception:
        pass

    await set_commands()

    external = os.getenv("RENDER_EXTERNAL_URL", "").rstrip("/")

    if external:
        webhook_url = f"{external}/telegram/webhook"

        await bot.set_webhook(
            url=webhook_url,
            secret_token=settings.webhook_secret or None,
            allowed_updates=dp.resolve_used_update_types(),
        )

    maintenance_task = asyncio.create_task(
        maintenance_loop(bot)
    )

    yield

    if maintenance_task:
        maintenance_task.cancel()

        try:
            await maintenance_task
        except asyncio.CancelledError:
            pass

    try:
        await bot.delete_webhook(
            drop_pending_updates=False
        )
    except Exception:
        pass

    await bot.session.close()


app = FastAPI(
    title="FAST SMM BOT",
    lifespan=lifespan,
)


@app.get("/health")
async def health():
    return {"ok": True}


@app.post("/telegram/webhook")
async def webhook(request: Request):
    if (
        settings.webhook_secret
        and request.headers.get(
            "X-Telegram-Bot-Api-Secret-Token",
            ""
        ) != settings.webhook_secret
    ):
        raise HTTPException(
            status_code=403,
            detail="forbidden"
        )

    update_data = await request.json()
    update = Update.model_validate(update_data)

    await dp.feed_update(
        bot,
        update
    )

    return JSONResponse(
        {"ok": True}
    )


if __name__ == "__main__":
    import uvicorn

    port = int(os.getenv("PORT", "10000"))

    uvicorn.run(
        app,
        host="0.0.0.0",
        port=port,
    )
