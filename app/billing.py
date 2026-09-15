from sqlalchemy import select
from .db import Session, User, Payment, Ledger, ReferralReward, now

REFERRAL_REWARD = 200

def bonus_for(amount: int) -> int:
    return (amount // 50_000) * 50

async def credit_payment(payment_id: int, admin_id: int):
    async with Session.begin() as s:
        p = await s.scalar(select(Payment).where(Payment.id == payment_id).with_for_update())
        if not p:
            return None, "not_found"
        if p.status != "pending":
            return p, "already_processed"
        u = await s.scalar(select(User).where(User.tg_id == p.user_tg_id).with_for_update())
        if not u:
            return None, "user_not_found"
        bonus = bonus_for(p.amount)
        total = p.amount + bonus
        u.balance += total
        p.status = "approved"
        p.confirmed_at = now()
        p.confirmed_by = admin_id
        p.bonus = bonus
        s.add(Ledger(user_tg_id=u.tg_id, kind="payment", amount=p.amount,
                     balance_after=u.balance, reference=f"payment:{p.id}", note=f"Payment #{p.id}"))
        if bonus:
            s.add(Ledger(user_tg_id=u.tg_id, kind="payment_bonus", amount=bonus,
                         balance_after=u.balance, reference=f"payment_bonus:{p.id}", note=f"Bonus for payment #{p.id}"))
        return p, "ok"

async def reject_payment(payment_id: int, admin_id: int):
    async with Session.begin() as s:
        p = await s.scalar(select(Payment).where(Payment.id == payment_id).with_for_update())
        if not p:
            return None, "not_found"
        if p.status != "pending":
            return p, "already_processed"
        p.status = "rejected"
        p.confirmed_at = now()
        p.confirmed_by = admin_id
        return p, "ok"

async def charge(user_id: int, amount: int, reference: str, note=""):
    if amount <= 0:
        return False
    async with Session.begin() as s:
        existing = await s.scalar(select(Ledger).where(Ledger.reference == reference))
        if existing:
            return True
        u = await s.scalar(select(User).where(User.tg_id == user_id).with_for_update())
        if not u or u.balance < amount:
            return False
        u.balance -= amount
        s.add(Ledger(user_tg_id=user_id, kind="charge", amount=-amount,
                     balance_after=u.balance, reference=reference, note=note))
        return True

async def refund(user_id: int, amount: int, reference: str, note=""):
    if amount <= 0:
        return False
    async with Session.begin() as s:
        if await s.scalar(select(Ledger).where(Ledger.reference == reference)):
            return True
        u = await s.scalar(select(User).where(User.tg_id == user_id).with_for_update())
        if not u:
            return False
        u.balance += amount
        s.add(Ledger(user_tg_id=user_id, kind="refund", amount=amount,
                     balance_after=u.balance, reference=reference, note=note))
        return True

async def reward_referral_if_eligible(user_id: int):
    async with Session.begin() as s:
        u = await s.scalar(select(User).where(User.tg_id == user_id).with_for_update())
        if not u or not u.registered or not u.referrer_id or u.referral_rewarded:
            return False
        ref = await s.scalar(select(User).where(User.tg_id == u.referrer_id).with_for_update())
        if not ref or not ref.registered or ref.tg_id == u.tg_id:
            return False
        if await s.scalar(select(ReferralReward).where(ReferralReward.referred_id == u.tg_id)):
            u.referral_rewarded = True
            return False
        ref.balance += REFERRAL_REWARD
        u.referral_rewarded = True
        s.add(ReferralReward(referrer_id=ref.tg_id, referred_id=u.tg_id,
                             amount=REFERRAL_REWARD, reference=f"referral:{u.tg_id}"))
        s.add(Ledger(user_tg_id=ref.tg_id, kind="referral", amount=REFERRAL_REWARD,
                     balance_after=ref.balance, reference=f"referral_ledger:{u.tg_id}",
                     note=f"Referral reward for {u.tg_id}"))
        return True
