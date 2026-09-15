from datetime import datetime, timezone
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column
from sqlalchemy import String, Integer, BigInteger, Boolean, DateTime, Text, Numeric, UniqueConstraint
from .config import settings

class Base(DeclarativeBase):
    pass

def now():
    return datetime.now(timezone.utc)

class User(Base):
    __tablename__ = "users"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    tg_id: Mapped[int] = mapped_column(BigInteger, unique=True, index=True)
    username: Mapped[str | None] = mapped_column(String(255))
    full_name: Mapped[str | None] = mapped_column(String(255))
    language: Mapped[str] = mapped_column(String(2), default="")
    phone: Mapped[str | None] = mapped_column(String(64))
    registered: Mapped[bool] = mapped_column(Boolean, default=False)
    blocked: Mapped[bool] = mapped_column(Boolean, default=False)
    referrer_id: Mapped[int | None] = mapped_column(BigInteger, index=True)
    referral_rewarded: Mapped[bool] = mapped_column(Boolean, default=False)
    is_admin: Mapped[bool] = mapped_column(Boolean, default=False)
    balance: Mapped[int] = mapped_column(BigInteger, default=0)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now, onupdate=now)

class MandatoryTarget(Base):
    __tablename__ = "mandatory_targets"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    chat_id: Mapped[int] = mapped_column(BigInteger, unique=True)
    title: Mapped[str] = mapped_column(String(255))
    username: Mapped[str | None] = mapped_column(String(255))
    target_type: Mapped[str] = mapped_column(String(30), default="channel")
    join_request: Mapped[bool] = mapped_column(Boolean, default=False)
    expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    active: Mapped[bool] = mapped_column(Boolean, default=True)

class Service(Base):
    __tablename__ = "services"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    provider_service_id: Mapped[str] = mapped_column(String(64), unique=True)
    name: Mapped[str] = mapped_column(String(500))
    category: Mapped[str | None] = mapped_column(String(255))
    api_rate: Mapped[Numeric | None] = mapped_column(Numeric(18, 4))
    markup_percent: Mapped[Numeric] = mapped_column(Numeric(8, 2), default=50)
    fixed_price: Mapped[int | None] = mapped_column(BigInteger)
    min_qty: Mapped[int | None] = mapped_column(Integer)
    max_qty: Mapped[int | None] = mapped_column(Integer)
    active: Mapped[bool] = mapped_column(Boolean, default=True)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now, onupdate=now)

class Product(Base):
    __tablename__ = "products"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    kind: Mapped[str] = mapped_column(String(30), index=True)
    code: Mapped[str] = mapped_column(String(100), unique=True)
    name_uz: Mapped[str] = mapped_column(String(255))
    name_ru: Mapped[str] = mapped_column(String(255))
    quantity: Mapped[int | None] = mapped_column(Integer)
    duration_months: Mapped[int | None] = mapped_column(Integer)
    price: Mapped[int] = mapped_column(BigInteger)
    gift_id: Mapped[str | None] = mapped_column(String(255))
    active: Mapped[bool] = mapped_column(Boolean, default=True)

class Payment(Base):
    __tablename__ = "payments"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_tg_id: Mapped[int] = mapped_column(BigInteger, index=True)
    amount: Mapped[int] = mapped_column(BigInteger)
    method: Mapped[str] = mapped_column(String(30))
    status: Mapped[str] = mapped_column(String(20), default="pending", index=True)
    receipt_file_id: Mapped[str | None] = mapped_column(String(500))
    receipt_type: Mapped[str | None] = mapped_column(String(20))
    confirmed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    confirmed_by: Mapped[int | None] = mapped_column(BigInteger)
    bonus: Mapped[int] = mapped_column(BigInteger, default=0)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)

class Ledger(Base):
    __tablename__ = "ledger"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_tg_id: Mapped[int] = mapped_column(BigInteger, index=True)
    kind: Mapped[str] = mapped_column(String(40))
    amount: Mapped[int] = mapped_column(BigInteger)
    balance_after: Mapped[int] = mapped_column(BigInteger)
    reference: Mapped[str] = mapped_column(String(150), unique=True)
    note: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)

class Order(Base):
    __tablename__ = "orders"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_tg_id: Mapped[int] = mapped_column(BigInteger, index=True)
    kind: Mapped[str] = mapped_column(String(30), index=True)
    product_code: Mapped[str | None] = mapped_column(String(100))
    provider_order_id: Mapped[str | None] = mapped_column(String(100), index=True)
    target: Mapped[str | None] = mapped_column(String(500))
    quantity: Mapped[int | None] = mapped_column(Integer)
    duration_months: Mapped[int | None] = mapped_column(Integer)
    price: Mapped[int] = mapped_column(BigInteger)
    status: Mapped[str] = mapped_column(String(30), default="pending", index=True)
    note: Mapped[str | None] = mapped_column(Text)
    proof_message_id: Mapped[int | None] = mapped_column(Integer)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now, onupdate=now)
    __table_args__ = (UniqueConstraint("provider_order_id", name="uq_provider_order_id"),)

class Setting(Base):
    __tablename__ = "settings"
    key: Mapped[str] = mapped_column(String(100), primary_key=True)
    value: Mapped[str] = mapped_column(Text)

class DailyBroadcast(Base):
    __tablename__ = "daily_broadcast"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_tg_id: Mapped[int] = mapped_column(BigInteger, unique=True)
    last_sent_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

class ReferralReward(Base):
    __tablename__ = "referral_rewards"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    referrer_id: Mapped[int] = mapped_column(BigInteger, index=True)
    referred_id: Mapped[int] = mapped_column(BigInteger, unique=True)
    amount: Mapped[int] = mapped_column(BigInteger, default=200)
    reference: Mapped[str] = mapped_column(String(150), unique=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)

engine = create_async_engine(settings.database_url, pool_pre_ping=True)
Session = async_sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)

async def init_db():
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
