import re
from aiogram import Router, F
from aiogram.filters import CommandStart
from aiogram.types import Message, CallbackQuery, ReplyKeyboardRemove, InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import StatesGroup, State
from sqlalchemy import select
from ..db import Session, User, MandatoryTarget, Payment, Order, Product, Service, Setting, Ledger, now
from ..keyboards import *
from ..i18n import t
from ..billing import reward_referral_if_eligible, charge, refund
from ..config import settings
from ..proof import post_order
from ..locksmm import add as api_add, status as api_status

router = Router()

class Reg(StatesGroup): phone = State()
class Pay(StatesGroup): amount = State(); receipt = State()
class Premium(StatesGroup): target = State(); confirm = State()
class Stars(StatesGroup): target = State(); confirm = State()
class Gift(StatesGroup): target = State(); confirm = State()
class ServiceOrder(StatesGroup): target = State(); quantity = State(); confirm = State()

async def get_user(uid):
    async with Session() as s:
        return await s.scalar(select(User).where(User.tg_id == uid))

async def ensure_user(message, ref=None):
    async with Session.begin() as s:
        u = await s.scalar(select(User).where(User.tg_id == message.from_user.id).with_for_update())
        if not u:
            u = User(tg_id=message.from_user.id, username=message.from_user.username,
                     full_name=message.from_user.full_name, is_admin=message.from_user.id in settings.admins)
            if ref and ref.isdigit() and int(ref) != message.from_user.id:
                inviter = await s.scalar(select(User).where(User.tg_id == int(ref)))
                if inviter:
                    u.referrer_id = inviter.tg_id
            s.add(u)
        else:
            u.username = message.from_user.username
            u.full_name = message.from_user.full_name
        return u

async def mandatory_ok(bot, uid):
    async with Session() as s:
        targets = (await s.scalars(select(MandatoryTarget).where(MandatoryTarget.active == True))).all()
    for x in targets:
        if x.expires_at and x.expires_at <= now():
            continue
        try:
            member = await bot.get_chat_member(x.chat_id, uid)
            if member.status in ("left", "kicked"):
                return False
            if member.status == "restricted" and getattr(member, "is_member", False) is False:
                return False
        except Exception:
            return False
    return True

async def show_subs(bot, uid, lang, chat_id):
    async with Session() as s:
        targets = (await s.scalars(select(MandatoryTarget).where(MandatoryTarget.active == True))).all()
    rows = []
    for x in targets:
        if x.expires_at and x.expires_at <= now():
            continue
        if x.username:
            rows.append([InlineKeyboardButton(text=f"📢 {x.title}", url=f"https://t.me/{x.username.lstrip('@')}")])
    rows.append([InlineKeyboardButton(text=t(lang, "check_sub"), callback_data="check_sub")])
    await bot.send_message(chat_id, t(lang, "subscribe"), reply_markup=InlineKeyboardMarkup(inline_keyboard=rows))

@router.message(CommandStart())
async def start(message: Message, state: FSMContext):
    arg = message.text.split(maxsplit=1)[1] if message.text and len(message.text.split()) > 1 else None
    u = await ensure_user(message, arg)
    if not u.language:
        await message.answer(t("uz", "choose_lang"), reply_markup=lang_kb())
        return
    if not u.registered:
        await state.clear()
        await message.answer(t(u.language, "choose_lang"), reply_markup=lang_kb())
        return
    if not await mandatory_ok(message.bot, message.from_user.id):
        await show_subs(message.bot, message.from_user.id, u.language, message.chat.id)
        return
    await message.answer(t(u.language, "menu"), reply_markup=main_kb(u.language))

@router.callback_query(F.data.startswith("lang:"))
async def choose_lang(cb: CallbackQuery, state: FSMContext):
    lang = cb.data.split(":", 1)[1]
    if lang not in ("uz", "ru"):
        await cb.answer("Invalid", show_alert=True); return
    async with Session.begin() as s:
        u = await s.scalar(select(User).where(User.tg_id == cb.from_user.id).with_for_update())
        if not u:
            await cb.answer("Qaytadan /start bosing", show_alert=True); return
        u.language = lang
    await cb.message.edit_text(t(lang, "share_phone"))
    await cb.message.answer(t(lang, "share_phone"), reply_markup=phone_kb(lang))
    await state.set_state(Reg.phone)
    await cb.answer()

@router.message(Reg.phone, F.contact)
async def phone(message: Message, state: FSMContext):
    u = await get_user(message.from_user.id)
    if not u:
        await message.answer("/start"); return
    c = message.contact
    if c.user_id != message.from_user.id:
        await message.answer(t(u.language, "wrong_contact")); return
    async with Session.begin() as s:
        x = await s.scalar(select(User).where(User.tg_id == message.from_user.id).with_for_update())
        x.phone = c.phone_number
    await message.answer(t(u.language, "registered"), reply_markup=ReplyKeyboardRemove())
    if not await mandatory_ok(message.bot, message.from_user.id):
        await show_subs(message.bot, message.from_user.id, u.language, message.chat.id)
        return
    async with Session.begin() as s:
        x = await s.scalar(select(User).where(User.tg_id == message.from_user.id).with_for_update())
        x.registered = True
    await state.clear()
    await reward_referral_if_eligible(message.from_user.id)
    await message.answer(t(u.language, "menu"), reply_markup=main_kb(u.language))

@router.message(Reg.phone)
async def phone_block(message: Message):
    u = await get_user(message.from_user.id)
    await message.answer(t(u.language if u else "uz", "wrong_contact"))

@router.callback_query(F.data == "check_sub")
async def check_sub(cb: CallbackQuery):
    u = await get_user(cb.from_user.id)
    if not u:
        await cb.answer("/start", show_alert=True); return
    if await mandatory_ok(cb.bot, cb.from_user.id):
        if not u.registered:
            async with Session.begin() as s:
                x=await s.scalar(select(User).where(User.tg_id==cb.from_user.id).with_for_update())
                if x: x.registered=True
            await reward_referral_if_eligible(cb.from_user.id)
            await cb.message.answer(t(u.language, "menu"), reply_markup=main_kb(u.language))
        else:
            await reward_referral_if_eligible(cb.from_user.id)
            await cb.message.answer(t(u.language, "menu"), reply_markup=main_kb(u.language))
        await cb.answer("✅")
    else:
        await cb.answer("❌ Obuna hali to‘liq emas.", show_alert=True)

@router.callback_query(F.data == "back:menu")
async def back_menu(cb: CallbackQuery):
    u = await get_user(cb.from_user.id)
    await cb.message.edit_text(t(u.language, "menu"), reply_markup=main_kb(u.language)); await cb.answer()

@router.callback_query(F.data == "menu:balance")
async def balance(cb: CallbackQuery):
    u = await get_user(cb.from_user.id)
    await cb.message.edit_text(f"💰 Balansingiz: <b>{u.balance:,} so‘m</b>", parse_mode="HTML",
                               reply_markup=InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text=t(u.language,"topup"), callback_data="menu:topup")],[InlineKeyboardButton(text=t(u.language,"back"), callback_data="back:menu")]])); await cb.answer()

@router.callback_query(F.data == "menu:topup")
async def topup(cb: CallbackQuery, state: FSMContext):
    u = await get_user(cb.from_user.id)
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🇺🇿 Karta orqali to‘lov", callback_data="paymethod:local")],
        [InlineKeyboardButton(text="🌎 Chet eldan to‘lov", callback_data="paymethod:foreign")],
        [InlineKeyboardButton(text="⬅️ Orqaga", callback_data="back:menu")]])
    await cb.message.edit_text("💳 Balansni to‘ldirish usulini tanlang:", reply_markup=kb); await cb.answer()

@router.callback_query(F.data.startswith("paymethod:"))
async def pay_method(cb: CallbackQuery, state: FSMContext):
    method = cb.data.split(":",1)[1]; u = await get_user(cb.from_user.id)
    if method == "local":
        cards = f"🇺🇿 HUMO: <code>{settings.humo_card}</code>\n👤 {settings.card_owner}"
    else:
        cards = f"🌎 Visa: <code>{settings.visa_card}</code>\n🌎 Mastercard: <code>{settings.mastercard_card}</code>\n👤 {settings.card_owner}"
    async with Session() as s:
        st = await s.get(Setting, "min_payment")
    minimum = int(st.value) if st and st.value.isdigit() else 2000
    await state.update_data(method=method)
    await cb.message.edit_text(t(u.language,"payment_amount",minimum=minimum)+"\n\n"+cards, parse_mode="HTML")
    await state.set_state(Pay.amount); await cb.answer()

@router.message(Pay.amount)
async def pay_amount(message: Message, state: FSMContext):
    u = await get_user(message.from_user.id)
    raw = (message.text or "").replace(" ","").replace(",","").replace(".","")
    if not raw.isdigit():
        await message.answer(t(u.language,"bad_amount")); return
    amount = int(raw)
    async with Session() as s: st = await s.get(Setting,"min_payment")
    minimum = int(st.value) if st and st.value.isdigit() else 2000
    if amount < minimum:
        await message.answer(f"❌ Minimal summa: {minimum:,} so‘m"); return
    data = await state.get_data()
    await state.update_data(amount=amount, method=data.get("method","local"))
    await message.answer(t(u.language,"send_receipt",amount=amount)); await state.set_state(Pay.receipt)

@router.message(Pay.receipt, F.photo)
@router.message(Pay.receipt, F.document)
async def pay_receipt(message: Message, state: FSMContext):
    u = await get_user(message.from_user.id); data = await state.get_data()
    if not u or "amount" not in data:
        await state.clear(); await message.answer("Qaytadan /start bosing."); return
    if message.photo: fid, typ = message.photo[-1].file_id, "photo"
    else: fid, typ = message.document.file_id, "document"
    async with Session.begin() as s:
        p = Payment(user_tg_id=u.tg_id, amount=int(data["amount"]), method=data.get("method","local"), receipt_file_id=fid, receipt_type=typ)
        s.add(p); await s.flush(); pid = p.id
    await state.clear(); await message.answer(t(u.language,"payment_sent"), reply_markup=main_kb(u.language))
    from .admin import notify_payment
    await notify_payment(message.bot, pid)

@router.message(Pay.receipt)
async def bad_receipt(message: Message):
    u = await get_user(message.from_user.id)
    await message.answer("🧾 Iltimos, chekni rasm yoki fayl sifatida yuboring.")

@router.callback_query(F.data == "menu:ref")
async def ref(cb: CallbackQuery):
    u = await get_user(cb.from_user.id); me = await cb.bot.get_me()
    link = f"https://t.me/{me.username}?start={u.tg_id}"
    await cb.message.edit_text(t(u.language,"ref_info",link=link), reply_markup=back(u.language)); await cb.answer()

async def insufficient(cb, u, price):
    await cb.message.edit_text(t(u.language,"no_balance",price=price,balance=u.balance,short=price-u.balance),
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text=t(u.language,"topup"),callback_data="menu:topup")]]))

@router.callback_query(F.data == "menu:premium")
async def premium(cb: CallbackQuery):
    u = await get_user(cb.from_user.id)
    async with Session() as s: ps=(await s.scalars(select(Product).where(Product.kind=="premium",Product.active==True).order_by(Product.duration_months))).all()
    rows=[[InlineKeyboardButton(text=f"💎 {p.name_uz} — {p.price:,} so‘m",callback_data=f"prem:{p.code}")] for p in ps]
    rows.append([InlineKeyboardButton(text="⬅️ Orqaga",callback_data="back:menu")])
    await cb.message.edit_text("💎 Telegram Premium",reply_markup=InlineKeyboardMarkup(inline_keyboard=rows)); await cb.answer()

@router.callback_query(F.data.startswith("prem:"))
async def premium_select(cb: CallbackQuery, state: FSMContext):
    code=cb.data.split(":",1)[1]; u=await get_user(cb.from_user.id)
    async with Session() as s: p=await s.scalar(select(Product).where(Product.code==code,Product.kind=="premium",Product.active==True))
    if not p: await cb.answer("❌ Xizmat topilmadi.",show_alert=True); return
    if p.duration_months==1:
        if u.balance<p.price: await insufficient(cb,u,p.price); return
        await state.update_data(product_code=code)
        await cb.message.edit_text(f"💎 1 oylik Premium\n💰 {p.price:,} so‘m\n\nTasdiqlaysizmi?",reply_markup=confirm("prem1_confirm",u.language)); await state.set_state(Premium.confirm)
    else:
        await state.update_data(product_code=code)
        await cb.message.edit_text("👤 Premium oladigan Telegram @username ni yuboring:")
        await state.set_state(Premium.target)
    await cb.answer()

@router.message(Premium.target)
async def prem_target(message: Message, state: FSMContext):
    u=await get_user(message.from_user.id); target=(message.text or "").strip()
    if not re.fullmatch(r"@[A-Za-z0-9_]{5,32}",target): await message.answer("❌ Username noto‘g‘ri. Masalan: @username"); return
    data=await state.get_data()
    async with Session() as s: p=await s.scalar(select(Product).where(Product.code==data.get("product_code")))
    if not p: await state.clear(); await message.answer("❌ Xizmat topilmadi."); return
    if u.balance<p.price: await message.answer(t(u.language,"no_balance",price=p.price,balance=u.balance,short=p.price-u.balance),reply_markup=InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text=t(u.language,"topup"),callback_data="menu:topup")]])); await state.clear(); return
    await state.update_data(target=target)
    await message.answer(f"💎 Premium\n⏳ {p.duration_months} oy\n👤 {target}\n💰 {p.price:,} so‘m\n\nTasdiqlaysizmi?",reply_markup=confirm("prem_confirm",u.language)); await state.set_state(Premium.confirm)

async def create_manual_order(cb, u, p, target, kind, note):
    reference=f"order:{kind}:{u.tg_id}:{p.code}:{target}"
    async with Session() as s:
        existing=await s.scalar(select(Order).where(Order.user_tg_id==u.tg_id,Order.kind==kind,Order.product_code==p.code,Order.target==target,Order.status.in_(["pending","processing","awaiting_admin"])))
    if existing:
        return existing
    if not await charge(u.tg_id,p.price,reference,note):
        return None
    async with Session.begin() as s:
        o=Order(user_tg_id=u.tg_id,kind=kind,product_code=p.code,target=target,quantity=p.quantity,duration_months=p.duration_months,price=p.price,status="awaiting_admin",note=note)
        s.add(o); await s.flush(); oid=o.id
    return await get_order(oid)

@router.callback_query(Premium.confirm,F.data.in_( {"prem_confirm:yes","prem1_confirm:yes"} ))
async def prem_confirm(cb: CallbackQuery,state: FSMContext):
    u=await get_user(cb.from_user.id); data=await state.get_data()
    async with Session() as s: p=await s.scalar(select(Product).where(Product.code==data.get("product_code"),Product.kind=="premium",Product.active==True))
    target = data.get("target") or "@"+settings.premium_admin_username
    if not p: await cb.answer("❌ Xizmat topilmadi.",show_alert=True); return
    order=await create_manual_order(cb,u,p,target,"premium","Premium admin fulfillment")
    if not order:
        await cb.answer("❌ Balans yetarli emas.",show_alert=True); return
    await post_order(cb.bot,order)
    for aid in settings.admins:
        try: await cb.bot.send_message(aid,f"💎 Premium buyurtma #{order.id}\n👤 Mijoz ID: {u.tg_id}\n🎯 {target}\n⏳ {p.duration_months} oy\n💰 {p.price:,} so‘m",reply_markup=admin_done(order.id))
        except Exception: pass
    if p.duration_months==1:
        url=f"https://t.me/{settings.premium_admin_username}?text=" + f"Assalomu%20alaykum.%20Bot%20orqali%20bir%20oylik%20Telegram%20Premium%20uchun%20to‘lov%20qildim.%20🆔%20Mening%20ID:%20{u.tg_id}"
        await cb.message.edit_text("💎 1 oylik Premium uchun to‘lov qabul qilindi.\n\n📩 Admin bilan bog‘laning va tayyor xabarni yuboring.",reply_markup=InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="📩 Admin bilan bog‘lanish",url=url)]]))
    else:
        await cb.message.edit_text("⏳ Buyurtmangiz 5–15 daqiqa ichida admin tomonidan bajariladi.")
    await state.clear(); await cb.answer()

@router.callback_query(Premium.confirm,F.data.in_({"prem_confirm:no","prem1_confirm:no"}))
async def prem_cancel(cb: CallbackQuery,state:FSMContext):
    u=await get_user(cb.from_user.id); await state.clear(); await cb.message.edit_text(t(u.language,"menu"),reply_markup=main_kb(u.language)); await cb.answer()

@router.callback_query(F.data == "menu:stars")
async def stars(cb: CallbackQuery):
    u=await get_user(cb.from_user.id)
    async with Session() as s: ps=(await s.scalars(select(Product).where(Product.kind=="stars",Product.active==True).order_by(Product.quantity))).all()
    rows=[[InlineKeyboardButton(text=f"⭐ {p.quantity} — {p.price:,} so‘m",callback_data=f"stars:{p.code}")] for p in ps]
    rows.append([InlineKeyboardButton(text="⬅️ Orqaga",callback_data="back:menu")])
    await cb.message.edit_text("⭐ Telegram Stars",reply_markup=InlineKeyboardMarkup(inline_keyboard=rows)); await cb.answer()

@router.callback_query(F.data.startswith("stars:"))
async def stars_select(cb: CallbackQuery,state: FSMContext):
    code=cb.data.split(":",1)[1]; u=await get_user(cb.from_user.id)
    async with Session() as s: p=await s.scalar(select(Product).where(Product.code==code,Product.kind=="stars",Product.active==True))
    if not p: await cb.answer("❌ Topilmadi",show_alert=True); return
    if u.balance<p.price: await insufficient(cb,u,p.price); return
    await state.update_data(product_code=code)
    await cb.message.edit_text(f"⭐ {p.quantity} Stars\n💰 {p.price:,} so‘m\n\nQabul qiluvchining @username sini yuboring:")
    await state.set_state(Stars.target); await cb.answer()

@router.message(Stars.target)
async def stars_target(message:Message,state:FSMContext):
    u=await get_user(message.from_user.id); target=(message.text or "").strip()
    if not re.fullmatch(r"@[A-Za-z0-9_]{5,32}",target): await message.answer("❌ Username noto‘g‘ri."); return
    data=await state.get_data()
    async with Session() as s: p=await s.scalar(select(Product).where(Product.code==data.get("product_code")))
    await state.update_data(target=target)
    await message.answer(f"⭐ {p.quantity} Stars\n👤 {target}\n💰 {p.price:,} so‘m\n\nTasdiqlaysizmi?",reply_markup=confirm("stars_confirm",u.language)); await state.set_state(Stars.confirm)

@router.callback_query(Stars.confirm,F.data=="stars_confirm:yes")
async def stars_confirm(cb:CallbackQuery,state:FSMContext):
    u=await get_user(cb.from_user.id); data=await state.get_data()
    async with Session() as s: p=await s.scalar(select(Product).where(Product.code==data.get("product_code"),Product.kind=="stars"))
    order=await create_manual_order(cb,u,p,data["target"],"stars","Stars admin fulfillment")
    if not order: await cb.answer("❌ Balans yetarli emas.",show_alert=True); return
    await post_order(cb.bot,order)
    for aid in settings.admins:
        try: await cb.bot.send_message(aid,f"⭐ Stars buyurtma #{order.id}\n👤 {u.tg_id}\n🎯 {data['target']}\n⭐ {p.quantity}\n💰 {p.price:,} so‘m",reply_markup=admin_done(order.id))
        except Exception: pass
    await cb.message.edit_text("⏳ Stars buyurtmangiz admin tomonidan bajariladi."); await state.clear(); await cb.answer()

@router.callback_query(Stars.confirm,F.data=="stars_confirm:no")
async def stars_cancel(cb:CallbackQuery,state:FSMContext):
    u=await get_user(cb.from_user.id); await state.clear(); await cb.message.edit_text(t(u.language,"menu"),reply_markup=main_kb(u.language)); await cb.answer()

@router.callback_query(F.data == "menu:gifts")
async def gifts(cb: CallbackQuery):
    async with Session() as s: ps=(await s.scalars(select(Product).where(Product.kind=="gift",Product.active==True))).all()
    rows=[[InlineKeyboardButton(text=f"🎁 {p.name_uz} — {p.price:,} so‘m",callback_data=f"gift:{p.code}")] for p in ps]
    rows.append([InlineKeyboardButton(text="⬅️ Orqaga",callback_data="back:menu")])
    await cb.message.edit_text("🎁 Telegram Gifts",reply_markup=InlineKeyboardMarkup(inline_keyboard=rows)); await cb.answer()

@router.callback_query(F.data.startswith("gift:"))
async def gift_select(cb:CallbackQuery,state:FSMContext):
    code=cb.data.split(":",1)[1]; u=await get_user(cb.from_user.id)
    async with Session() as s: p=await s.scalar(select(Product).where(Product.code==code,Product.kind=="gift",Product.active==True))
    if not p: await cb.answer("❌ Topilmadi",show_alert=True); return
    if u.balance<p.price: await insufficient(cb,u,p.price); return
    await state.update_data(product_code=code)
    await cb.message.edit_text(f"🎁 {p.name_uz}\n💰 {p.price:,} so‘m\n\nQabul qiluvchining @username sini yuboring:"); await state.set_state(Gift.target); await cb.answer()

@router.message(Gift.target)
async def gift_target(message:Message,state:FSMContext):
    u=await get_user(message.from_user.id); target=(message.text or "").strip()
    if not re.fullmatch(r"@[A-Za-z0-9_]{5,32}",target): await message.answer("❌ Username noto‘g‘ri."); return
    data=await state.get_data()
    async with Session() as s: p=await s.scalar(select(Product).where(Product.code==data.get("product_code")))
    await state.update_data(target=target)
    await message.answer(f"🎁 {p.name_uz}\n👤 {target}\n💰 {p.price:,} so‘m\n\nTasdiqlaysizmi?",reply_markup=confirm("gift_confirm",u.language)); await state.set_state(Gift.confirm)

@router.callback_query(Gift.confirm,F.data=="gift_confirm:yes")
async def gift_confirm(cb:CallbackQuery,state:FSMContext):
    u=await get_user(cb.from_user.id); data=await state.get_data()
    async with Session() as s: p=await s.scalar(select(Product).where(Product.code==data.get("product_code"),Product.kind=="gift"))
    order=await create_manual_order(cb,u,p,data["target"],"gift","Gift admin fulfillment")
    if not order: await cb.answer("❌ Balans yetarli emas.",show_alert=True); return
    await post_order(cb.bot,order)
    for aid in settings.admins:
        try: await cb.bot.send_message(aid,f"🎁 Gift buyurtma #{order.id}\n👤 {u.tg_id}\n🎯 {data['target']}\n🎁 {p.name_uz}\n💰 {p.price:,} so‘m",reply_markup=admin_done(order.id))
        except Exception: pass
    await cb.message.edit_text("⏳ Gift buyurtmangiz admin tomonidan bajariladi."); await state.clear(); await cb.answer()

@router.callback_query(Gift.confirm,F.data=="gift_confirm:no")
async def gift_cancel(cb:CallbackQuery,state:FSMContext):
    u=await get_user(cb.from_user.id); await state.clear(); await cb.message.edit_text(t(u.language,"menu"),reply_markup=main_kb(u.language)); await cb.answer()

@router.callback_query(F.data == "menu:services")
async def services_menu(cb:CallbackQuery):
    u=await get_user(cb.from_user.id)
    async with Session() as s: ss=(await s.scalars(select(Service).where(Service.active==True).order_by(Service.id))).all()
    rows=[]
    for x in ss[:80]:
        price = int(round(float(x.fixed_price) if x.fixed_price else float(x.api_rate or 0) * (1+float(x.markup_percent)/100)))
        rows.append([InlineKeyboardButton(text=f"📦 {x.name[:42]} — {price:,}",callback_data=f"svc:{x.id}")])
    rows.append([InlineKeyboardButton(text="⬅️ Orqaga",callback_data="back:menu")])
    await cb.message.edit_text("📦 SMM xizmatlari",reply_markup=InlineKeyboardMarkup(inline_keyboard=rows)); await cb.answer()

@router.callback_query(F.data.startswith("svc:"))
async def svc_select(cb:CallbackQuery,state:FSMContext):
    sid=int(cb.data.split(":",1)[1])
    async with Session() as s: x=await s.get(Service,sid)
    if not x or not x.active: await cb.answer("❌ Xizmat mavjud emas.",show_alert=True); return
    await state.update_data(service_id=sid)
    await cb.message.edit_text(f"📦 {x.name}\n🔢 Miqdor: {x.min_qty}–{x.max_qty}\n\n🔗 Linkni yuboring:"); await state.set_state(ServiceOrder.target); await cb.answer()

@router.message(ServiceOrder.target)
async def svc_target(message:Message,state:FSMContext):
    target=(message.text or "").strip()
    if not (target.startswith("http://") or target.startswith("https://")):
        await message.answer("❌ To‘g‘ri havola yuboring."); return
    await state.update_data(target=target); await message.answer("🔢 Miqdorni yuboring:"); await state.set_state(ServiceOrder.quantity)

@router.message(ServiceOrder.quantity)
async def svc_qty(message:Message,state:FSMContext):
    raw=(message.text or "").strip()
    if not raw.isdigit(): await message.answer("❌ Miqdor son bo‘lishi kerak."); return
    q=int(raw); data=await state.get_data()
    async with Session() as s: x=await s.get(Service,int(data["service_id"]))
    if not x: await state.clear(); await message.answer("❌ Xizmat topilmadi."); return
    if q<x.min_qty or q>x.max_qty: await message.answer(f"❌ Miqdor {x.min_qty}–{x.max_qty} oralig‘ida bo‘lishi kerak."); return
    raw_price=float(x.fixed_price) if x.fixed_price else float(x.api_rate or 0)*(q/1000)*(1+float(x.markup_percent)/100)
    price=max(1,int(round(raw_price)))
    await state.update_data(quantity=q,price=price)
    await message.answer(f"📦 {x.name}\n🔢 {q}\n💰 {price:,} so‘m\n\nTasdiqlaysizmi?",reply_markup=confirm("svc_confirm",(await get_user(message.from_user.id)).language)); await state.set_state(ServiceOrder.confirm)

@router.callback_query(ServiceOrder.confirm,F.data=="svc_confirm:yes")
async def svc_confirm(cb:CallbackQuery,state:FSMContext):
    data=await state.get_data(); u=await get_user(cb.from_user.id); price=int(data["price"])
    reference=f"order:smm:{u.tg_id}:{data['service_id']}:{data['target']}:{data['quantity']}"
    if not await charge(u.tg_id,price,reference,"SMM order"):
        await cb.answer("❌ Balans yetarli emas.",show_alert=True); return
    try:
        res=await api_add(str(data["service_id"]),data["target"],int(data["quantity"]))
        provider=str(res.get("order")) if isinstance(res,dict) else ""
        if not provider: raise RuntimeError(str(res))
    except Exception as exc:
        await refund(u.tg_id,price,f"refund:{reference}",f"Provider add failed: {str(exc)[:300]}")
        await cb.message.edit_text("❌ API orqali buyurtma yaratilmadi. Mablag‘ingiz balansga qaytarildi."); await state.clear(); await cb.answer(); return
    async with Session.begin() as s:
        o=Order(user_tg_id=u.tg_id,kind="smm",product_code=str(data["service_id"]),provider_order_id=provider,target=data["target"],quantity=data["quantity"],price=price,status="processing")
        s.add(o); await s.flush(); oid=o.id
    await post_order(cb.bot,await get_order(oid))
    await cb.message.edit_text(t(u.language,"order_created",order=oid,price=price)); await state.clear(); await cb.answer()

@router.callback_query(ServiceOrder.confirm,F.data=="svc_confirm:no")
async def svc_cancel(cb:CallbackQuery,state:FSMContext):
    u=await get_user(cb.from_user.id); await state.clear(); await cb.message.edit_text(t(u.language,"menu"),reply_markup=main_kb(u.language)); await cb.answer()

async def get_order(oid):
    async with Session() as s: return await s.get(Order,oid)

@router.callback_query(F.data.startswith("order_status:"))
async def order_status(cb:CallbackQuery):
    try: oid=int(cb.data.split(":",1)[1])
    except: await cb.answer("❌",show_alert=True); return
    async with Session() as s: o=await s.get(Order,oid)
    if not o: await cb.answer("❌ Buyurtma topilmadi.",show_alert=True); return
    if o.kind=="smm" and o.provider_order_id and o.status not in ("done","cancelled"):
        try:
            data=await api_status(order=o.provider_order_id)
            item=data.get(o.provider_order_id) if isinstance(data,dict) else data
            raw=(item.get("status","") if isinstance(item,dict) else str(item)).lower()
            new="done" if "complete" in raw else "cancelled" if ("cancel" in raw or "fail" in raw) else "processing"
            async with Session.begin() as s:
                x=await s.get(Order,oid,with_for_update=True)
                if x: x.status=new
            o.status=new
        except Exception: pass
    labels={"processing":"🟡 Jarayonda","done":"🟢 Bajarildi","cancelled":"🔴 Bekor qilindi","awaiting_admin":"🟡 Admin bajarishini kutmoqda","pending":"🟡 Kutilmoqda"}
    await cb.answer(labels.get(o.status,"🟡 Jarayonda"),show_alert=True)
