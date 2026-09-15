from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton, ReplyKeyboardMarkup, KeyboardButton

def lang_kb():
    return InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="🇺🇿 O‘zbekcha", callback_data="lang:uz"), InlineKeyboardButton(text="🇷🇺 Русский", callback_data="lang:ru")]])

def phone_kb(lang):
    text = "📱 Telefon raqamimni yuborish" if lang == "uz" else "📱 Отправить мой номер"
    return ReplyKeyboardMarkup(keyboard=[[KeyboardButton(text=text, request_contact=True)]], resize_keyboard=True, one_time_keyboard=True)

def main_kb(lang):
    labels = {
        "uz": [("💰 Balansim","menu:balance"),("💳 Balansni to‘ldirish","menu:topup"),("📦 SMM xizmatlari","menu:services"),
               ("⭐ Telegram Stars","menu:stars"),("🎁 Telegram Gifts","menu:gifts"),("💎 Telegram Premium","menu:premium"),
               ("👥 Referal","menu:ref"),("ℹ️ Yordam","menu:help")],
        "ru": [("💰 Баланс","menu:balance"),("💳 Пополнить","menu:topup"),("📦 SMM услуги","menu:services"),
               ("⭐ Telegram Stars","menu:stars"),("🎁 Telegram Gifts","menu:gifts"),("💎 Telegram Premium","menu:premium"),
               ("👥 Реферал","menu:ref"),("ℹ️ Помощь","menu:help")]
    }
    return InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text=a, callback_data=b)] for a,b in labels[lang]])

def back(lang="uz"):
    return InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="⬅️ Orqaga" if lang=="uz" else "⬅️ Назад", callback_data="back:menu")]])

def confirm(prefix, lang="uz"):
    yes = "✅ Ha, tasdiqlash" if lang == "uz" else "✅ Да, подтвердить"
    no = "❌ Bekor qilish" if lang == "uz" else "❌ Отмена"
    return InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text=yes, callback_data=f"{prefix}:yes"), InlineKeyboardButton(text=no, callback_data=f"{prefix}:no")]])

def admin_payment(pid):
    return InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="✅ Tasdiqlash", callback_data=f"pay:{pid}:approve"), InlineKeyboardButton(text="❌ Rad etish", callback_data=f"pay:{pid}:reject")]])

def status(order_id):
    return InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="📊 Holatni ko‘rish", callback_data=f"order_status:{order_id}")]])

def admin_done(order_id):
    return InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="✅ Buyurtma bajarildi", callback_data=f"admin_done:{order_id}")]])
