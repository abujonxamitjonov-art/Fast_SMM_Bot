import asyncio
from datetime import datetime
from zoneinfo import ZoneInfo
from aiogram import Router, F, Bot
from aiogram.filters import Command
from aiogram.types import Message, CallbackQuery
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import StatesGroup, State
from sqlalchemy import select, func
from ..config import settings
from ..db import Session, Payment, User, Order, MandatoryTarget, Service, Product, Ledger, Setting, now
from ..billing import credit_payment, reject_payment
from ..keyboards import admin_payment, confirm, admin_done
from ..catalog import sync_services

router=Router()
TASHKENT=ZoneInfo("Asia/Tashkent")

def admin_only(msg): return msg.from_user.id in settings.admins

async def notify_payment(bot:Bot,pid:int):
    async with Session() as s:
        p=await s.get(Payment,pid)
    if not p: return
    for aid in settings.admins:
        try:
            text=f"💳 <b>Yangi to‘lov #{pid}</b>\n👤 Mijoz: <code>{p.user_tg_id}</code>\n💰 Summa: <b>{p.amount:,} so‘m</b>\n💳 Usul: {p.method}"
            if p.receipt_type=="photo": await bot.send_photo(aid,p.receipt_file_id,caption=text,parse_mode="HTML",reply_markup=admin_payment(pid))
            else: await bot.send_document(aid,p.receipt_file_id,caption=text,parse_mode="HTML",reply_markup=admin_payment(pid))
        except Exception: pass

class Broadcast(StatesGroup): message=State()

@router.message(Command("xizmatlar"))
async def services_cmd(m:Message):
    if not admin_only(m): return
    async with Session() as s: ss=(await s.scalars(select(Service).order_by(Service.id))).all()
    if not ss: await m.answer("📦 Xizmatlar topilmadi. /xizmatlarni_yangilash bosing."); return
    lines=[]
    for x in ss[:100]:
        selling=int(round(float(x.fixed_price) if x.fixed_price else float(x.api_rate or 0)*(1+float(x.markup_percent)/100)))
        lines.append(f"#{x.id} | API {x.provider_service_id} | {x.name[:45]} | {selling:,} so‘m | {'ON' if x.active else 'OFF'}")
    await m.answer("\n".join(lines)[:4000])

@router.message(Command("xizmat"))
async def service_cmd(m:Message):
    if not admin_only(m): return
    p=m.text.split()
    if len(p)!=2 or not p[1].isdigit(): await m.answer("Foydalanish: /xizmat ID"); return
    async with Session() as s: x=await s.get(Service,int(p[1]))
    if not x: await m.answer("❌ Xizmat topilmadi."); return
    selling=int(round(float(x.fixed_price) if x.fixed_price else float(x.api_rate or 0)*(1+float(x.markup_percent)/100)))
    await m.answer(f"ID: {x.id}\nAPI ID: {x.provider_service_id}\nNomi: {x.name}\nAPI narx/1000: {x.api_rate}\nUstama: {x.markup_percent}%\nSotuv/1000: {selling:,} so‘m\nMin: {x.min_qty}\nMax: {x.max_qty}\nHolat: {'ON' if x.active else 'OFF'}")

@router.message(Command("ustama"))
async def markup_cmd(m:Message):
    if not admin_only(m): return
    p=m.text.split()
    if len(p)!=2: await m.answer("Foydalanish: /ustama 50"); return
    try: val=float(p[1])
    except ValueError: await m.answer("❌ Foiz noto‘g‘ri."); return
    if not 0<=val<=1000: await m.answer("❌ 0–1000 oralig‘ida kiriting."); return
    async with Session.begin() as s:
        x=await s.get(Setting,"global_markup")
        if x: x.value=str(val)
        else: s.add(Setting(key="global_markup",value=str(val)))
        for svc in (await s.scalars(select(Service))).all():
            if svc.fixed_price is None: svc.markup_percent=val
    await m.answer(f"✅ Ustama {val:g}% qilib o‘rnatildi.")

@router.message(Command("api_holati"))
async def api_status_cmd(m:Message):
    if not admin_only(m): return
    try:
        from ..locksmm import balance
        d=await balance(); await m.answer(f"🟢 Locksmm API ishlayapti.\n{d}")
    except Exception as e: await m.answer(f"🔴 API xatosi: {str(e)[:500]}")

@router.message(Command("xizmatlarni_yangilash"))
async def sync_cmd(m:Message):
    if not admin_only(m): return
    try: await sync_services(); await m.answer("✅ Xizmatlar API'dan yangilandi.")
    except Exception as e: await m.answer(f"❌ Yangilashda xato: {str(e)[:500]}")

@router.message(Command("tolovlar"))
async def payments_cmd(m:Message):
    if not admin_only(m): return
    async with Session() as s: ps=(await s.scalars(select(Payment).order_by(Payment.id.desc()).limit(50))).all()
    await m.answer("\n".join(f"#{p.id} | {p.user_tg_id} | {p.amount:,} | {p.status}" for p in ps) or "To‘lovlar yo‘q.")

@router.message(Command("tolov"))
async def payment_cmd(m:Message):
    if not admin_only(m): return
    p=m.text.split()
    if len(p)!=2 or not p[1].isdigit(): await m.answer("Foydalanish: /tolov ID"); return
    async with Session() as s: x=await s.get(Payment,int(p[1]))
    if not x: await m.answer("❌ Topilmadi."); return
    await m.answer(f"💳 To‘lov #{x.id}\n👤 {x.user_tg_id}\n💰 {x.amount:,}\n📌 {x.status}",reply_markup=admin_payment(x.id) if x.status=="pending" else None)

@router.callback_query(F.data.startswith("pay:"))
async def pay_action(cb:CallbackQuery):
    if cb.from_user.id not in settings.admins: await cb.answer("Ruxsat yo‘q.",show_alert=True); return
    _,pid,action=cb.data.split(":")
    await cb.message.answer("Ishonchingiz komilmi?",reply_markup=confirm(f"payconfirm:{pid}:{action}"))
    await cb.answer()

@router.callback_query(F.data.startswith("payconfirm:"))
async def pay_confirm(cb:CallbackQuery):
    if cb.from_user.id not in settings.admins: await cb.answer("Ruxsat yo‘q.",show_alert=True); return
    _,pid,action,answer=cb.data.split(":")
    if answer=="no": await cb.message.edit_text("❌ Bekor qilindi. To‘lov o‘zgarishsiz qoldi."); await cb.answer(); return
    pid=int(pid)
    p,res=await (credit_payment(pid,cb.from_user.id) if action=="approve" else reject_payment(pid,cb.from_user.id))
    if res=="already_processed": await cb.message.edit_text("⚠️ Bu to‘lov allaqachon qayta ishlangan."); await cb.answer(); return
    if res!="ok": await cb.message.edit_text("❌ To‘lov topilmadi."); await cb.answer(); return
    if action=="approve":
        async with Session() as s: u=await s.scalar(select(User).where(User.tg_id==p.user_tg_id))
        try: await cb.bot.send_message(p.user_tg_id,f"🎉 To‘lovingiz tasdiqlandi!\n💰 {p.amount:,} so‘m qo‘shildi.\n🎁 Bonus: {p.bonus:,} so‘m\n💳 Joriy balans: {u.balance:,} so‘m")
        except Exception: pass
        await cb.message.edit_text(f"✅ To‘lov #{pid} tasdiqlandi. {p.amount:,} + {p.bonus:,} bonus balansga qo‘shildi.")
    else:
        try: await cb.bot.send_message(p.user_tg_id,"❌ To‘lovingiz rad etildi.")
        except Exception: pass
        await cb.message.edit_text(f"❌ To‘lov #{pid} rad etildi.")
    await cb.answer()

@router.message(Command("buyurtmalar"))
async def orders_cmd(m:Message):
    if not admin_only(m): return
    async with Session() as s: os=(await s.scalars(select(Order).order_by(Order.id.desc()).limit(100))).all()
    await m.answer("\n".join(f"#{o.id} | {o.user_tg_id} | {o.kind} | {o.price:,} | {o.status}" for o in os) or "Buyurtmalar yo‘q.")

@router.message(Command("buyurtma"))
async def order_cmd(m:Message):
    if not admin_only(m): return
    p=m.text.split()
    if len(p)!=2 or not p[1].isdigit(): await m.answer("Foydalanish: /buyurtma ID"); return
    async with Session() as s:o=await s.get(Order,int(p[1]))
    if not o: await m.answer("❌ Buyurtma topilmadi."); return
    await m.answer(f"#{o.id}\n👤 {o.user_tg_id}\n📦 {o.kind}\n🎯 {o.target or '-'}\n🔢 {o.quantity or o.duration_months or '-'}\n💰 {o.price:,}\n📌 {o.status}\nAPI order: {o.provider_order_id or '-'}",reply_markup=admin_done(o.id) if o.status not in ("done","cancelled") else None)

@router.message(Command("buyurtma_holati"))
async def order_status_cmd(m:Message):
    if not admin_only(m): return
    p=m.text.split()
    if len(p)!=2 or not p[1].isdigit(): await m.answer("Foydalanish: /buyurtma_holati ID"); return
    async with Session() as s:o=await s.get(Order,int(p[1]))
    if not o: await m.answer("❌ Topilmadi."); return
    await m.answer(f"🆔 #{o.id}\n📌 {o.status}")

@router.callback_query(F.data.startswith("admin_done:"))
async def admin_done_cb(cb:CallbackQuery):
    if cb.from_user.id not in settings.admins: await cb.answer("Ruxsat yo‘q.",show_alert=True); return
    oid=int(cb.data.split(":",1)[1])
    async with Session.begin() as s:
        o=await s.get(Order,oid,with_for_update=True)
        if not o: await cb.answer("Topilmadi.",show_alert=True); return
        if o.status=="done": await cb.answer("Allaqachon bajarilgan.",show_alert=True); return
        if o.status=="cancelled": await cb.answer("Buyurtma bekor qilingan.",show_alert=True); return
        o.status="done"; uid=o.user_tg_id
    try: await cb.bot.send_message(uid,f"🎉 Buyurtmangiz muvaffaqiyatli bajarildi!\n🆔 #{oid}")
    except Exception: pass
    await cb.message.edit_reply_markup(reply_markup=None); await cb.answer("Bajarildi.")

@router.message(Command("foydalanuvchilar"))
async def users_cmd(m:Message):
    if not admin_only(m): return
    async with Session() as s:
        n=await s.scalar(select(func.count()).select_from(User)); users=(await s.scalars(select(User).order_by(User.id.desc()).limit(50))).all()
    text=f"👥 Jami: {n}\n\n"+"\n".join(f"{u.tg_id} | @{u.username or '-'} | {u.balance:,} | {'OK' if u.registered else 'REG YO‘Q'}" for u in users)
    await m.answer(text[:4000])

@router.message(Command("foydalanuvchi"))
async def user_cmd(m:Message):
    if not admin_only(m): return
    p=m.text.split()
    if len(p)!=2 or not p[1].isdigit(): await m.answer("Foydalanish: /foydalanuvchi ID"); return
    async with Session() as s:u=await s.scalar(select(User).where(User.tg_id==int(p[1])))
    if not u: await m.answer("❌ Topilmadi."); return
    await m.answer(f"ID: {u.tg_id}\nUsername: @{u.username or '-'}\nTelefon: {u.phone or '-'}\nBalans: {u.balance:,}\nTil: {u.language}\nRo‘yxatdan o‘tgan: {u.registered}")

@router.message(Command("balans"))
async def bal_cmd(m:Message):
    if not admin_only(m): return
    p=m.text.split()
    if len(p)!=2 or not p[1].isdigit(): await m.answer("Foydalanish: /balans ID"); return
    async with Session() as s:u=await s.scalar(select(User).where(User.tg_id==int(p[1])))
    await m.answer(f"💰 {u.balance:,} so‘m" if u else "❌ Topilmadi.")

@router.message(Command("balans_qoshish"))
async def add_bal(m:Message):
    if not admin_only(m): return
    p=m.text.split()
    if len(p)!=3 or not p[1].isdigit() or not p[2].isdigit() or int(p[2])<=0: await m.answer("Foydalanish: /balans_qoshish ID SUMMA"); return
    uid,amt=int(p[1]),int(p[2])
    async with Session.begin() as s:
        u=await s.scalar(select(User).where(User.tg_id==uid).with_for_update())
        if not u: await m.answer("❌ Topilmadi."); return
        ref=f"admin_credit:{m.from_user.id}:{uid}:{int(now().timestamp()*1000000)}"
        u.balance+=amt; s.add(Ledger(user_tg_id=uid,kind="admin_credit",amount=amt,balance_after=u.balance,reference=ref,note="Admin balance credit"))
    await m.answer("✅ Balans qo‘shildi.")

@router.message(Command("balans_ayirish"))
async def sub_bal(m:Message):
    if not admin_only(m): return
    p=m.text.split()
    if len(p)!=3 or not p[1].isdigit() or not p[2].isdigit() or int(p[2])<=0: await m.answer("Foydalanish: /balans_ayirish ID SUMMA"); return
    uid,amt=int(p[1]),int(p[2])
    async with Session.begin() as s:
        u=await s.scalar(select(User).where(User.tg_id==uid).with_for_update())
        if not u or u.balance<amt: await m.answer("❌ Balans yetarli emas yoki user topilmadi."); return
        ref=f"admin_debit:{m.from_user.id}:{uid}:{int(now().timestamp()*1000000)}"
        u.balance-=amt; s.add(Ledger(user_tg_id=uid,kind="admin_debit",amount=-amt,balance_after=u.balance,reference=ref,note="Admin balance debit"))
    await m.answer("✅ Balans ayrildi.")

@router.message(Command("kanallar"))
async def channels(m:Message):
    if not admin_only(m): return
    async with Session() as s: xs=(await s.scalars(select(MandatoryTarget).order_by(MandatoryTarget.id))).all()
    await m.answer("\n".join(f"#{x.id} {x.title} | {x.chat_id} | {'ON' if x.active else 'OFF'} | {x.expires_at or '-'}" for x in xs) or "Majburiy obuna yo‘q.")

@router.message(Command("kanal_qoshish"))
async def channel_add(m:Message):
    if not admin_only(m): return
    # /kanal_qoshish CHAT_ID NOMI [zayavka] [YYYY-MM-DD HH:MM]
    p=m.text.split(maxsplit=4)
    if len(p)<3: await m.answer("Foydalanish: /kanal_qoshish CHAT_ID NOMI [zayavka] [2026-09-15 18:00]"); return
    try:
        if p[1].startswith("@"):
            chat=await m.bot.get_chat(p[1]); cid=chat.id; username=p[1].lstrip("@"); auto_title=chat.title or p[2]
        else:
            cid=int(p[1]); chat=await m.bot.get_chat(cid); username=getattr(chat,"username",None); auto_title=chat.title or p[2]
    except Exception:
        await m.answer("❌ Bot chatni topa olmadi. Botni kanal/guruhga admin qiling va qayta urinib ko‘ring."); return
    title=p[2] if p[2] else auto_title; join_request=len(p)>3 and p[3].lower()=="zayavka"; exp=None
    if len(p)>4:
        try: exp=datetime.strptime(p[4],"%Y-%m-%d %H:%M").replace(tzinfo=TASHKENT).astimezone()
        except ValueError: await m.answer("❌ Sana: YYYY-MM-DD HH:MM"); return
    async with Session.begin() as s:
        x=await s.scalar(select(MandatoryTarget).where(MandatoryTarget.chat_id==cid))
        if x:
            x.active=True; x.title=title; x.username=username; x.join_request=join_request; x.expires_at=exp
        else:
            s.add(MandatoryTarget(chat_id=cid,title=title,username=username,join_request=join_request,expires_at=exp))
    await m.answer("✅ Majburiy obuna qo‘shildi.")

@router.message(Command("kanal_ochirish"))
async def channel_del(m:Message):
    if not admin_only(m): return
    p=m.text.split()
    if len(p)!=2 or not p[1].isdigit(): await m.answer("Foydalanish: /kanal_ochirish ID"); return
    async with Session.begin() as s:
        x=await s.get(MandatoryTarget,int(p[1]))
        if not x: await m.answer("❌ Topilmadi."); return
        x.active=False
    await m.answer("✅ O‘chirildi.")

@router.message(Command("reklama"))
async def broadcast_start(m:Message,state:FSMContext):
    if not admin_only(m): return
    await state.set_state(Broadcast.message); await m.answer("📢 Tarqatiladigan xabarni yuboring. Format va custom emoji saqlanadi.")

@router.message(Broadcast.message)
async def broadcast_send(m:Message,state:FSMContext):
    if not admin_only(m): return
    async with Session() as s: users=(await s.scalars(select(User).where(User.registered==True,User.blocked==False))).all()
    ok=bad=0
    for u in users:
        if u.tg_id in settings.admins: continue
        try: await m.bot.copy_message(u.tg_id,m.chat.id,m.message_id); ok+=1
        except Exception: bad+=1
        await asyncio.sleep(.05)
    await state.clear(); await m.answer(f"✅ Tarqatildi: {ok}\n❌ Yetkazilmadi: {bad}")

@router.message(Command("bloklash"))
async def block_user(m:Message):
    if not admin_only(m): return
    p=m.text.split()
    if len(p)!=2 or not p[1].isdigit(): await m.answer("Foydalanish: /bloklash ID"); return
    async with Session.begin() as s:
        u=await s.scalar(select(User).where(User.tg_id==int(p[1])))
        if not u: await m.answer("❌ Topilmadi."); return
        u.blocked=True
    await m.answer("✅ Foydalanuvchi bloklandi.")

@router.message(Command("blokdan_chiqarish"))
async def unblock_user(m:Message):
    if not admin_only(m): return
    p=m.text.split()
    if len(p)!=2 or not p[1].isdigit(): await m.answer("Foydalanish: /blokdan_chiqarish ID"); return
    async with Session.begin() as s:
        u=await s.scalar(select(User).where(User.tg_id==int(p[1])))
        if not u: await m.answer("❌ Topilmadi."); return
        u.blocked=False
    await m.answer("✅ Foydalanuvchi blokdan chiqarildi.")

@router.message(Command("xabar"))
async def direct_message(m:Message):
    if not admin_only(m): return
    p=m.text.split(maxsplit=2)
    if len(p)<3 or not p[1].isdigit(): await m.answer("Foydalanish: /xabar ID MATN"); return
    try: await m.bot.send_message(int(p[1]),p[2]); await m.answer("✅ Xabar yuborildi.")
    except Exception as e: await m.answer(f"❌ Yuborilmadi: {str(e)[:300]}")

@router.message(Command("minimal_tolov"))
async def min_payment(m:Message):
    if not admin_only(m): return
    p=m.text.split()
    if len(p)==1:
        async with Session() as s:x=await s.get(Setting,"min_payment")
        await m.answer(f"Minimal to‘lov: {int(x.value):,} so‘m" if x else "2 000 so‘m"); return
    if not p[1].isdigit() or int(p[1])<0: await m.answer("❌ Summa noto‘g‘ri."); return
    async with Session.begin() as s:
        x=await s.get(Setting,"min_payment")
        if x: x.value=p[1]
        else: s.add(Setting(key="min_payment",value=p[1]))
    await m.answer(f"✅ Minimal to‘lov {int(p[1]):,} so‘m.")

@router.message(Command("sozlamalar"))
async def settings_cmd(m:Message):
    if not admin_only(m): return
    await m.answer(f"👨‍💼 Adminlar: {', '.join(map(str,settings.admins))}\n💎 Premium admin: @{settings.premium_admin_username}\n💳 Karta egasi: {settings.card_owner}\n📢 Proof kanal: {settings.proof_channel_id}")
