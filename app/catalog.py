from decimal import Decimal
from sqlalchemy import select
from .db import Session, Product, Service, Setting
from .locksmm import services as api_services

PREMIUM = [
    ("premium_1", "1 oy", 1, 48_000), ("premium_3", "3 oy", 3, 175_000),
    ("premium_6", "6 oy", 6, 230_000), ("premium_12", "12 oy", 12, 389_000),
]
STARS = [(50,14000),(100,26000),(150,39000),(200,50000),(250,62000),(300,75000),(350,86000),
         (400,98000),(450,109000),(500,121000),(600,143000),(700,168000),(800,190000),
         (900,214000),(1000,239000),(1500,350000),(2000,472000),(2500,589000),(3000,692000)]
GIFTS = [
    ("gift_15_bear", "Ayiqcha", 15, 5000), ("gift_15_pinkheart", "Pushti yurak", 15, 5000),
    ("gift_25_box", "Sovg‘a qutisi", 25, 9000), ("gift_25_rose", "Atirgul", 25, 9000),
    ("gift_50_cake", "Tort", 50, 16000), ("gift_50_bouquet", "Guldasta", 50, 16000),
    ("gift_50_rocket", "Raketa", 50, 16000), ("gift_100_cup", "Kubok", 100, 26000),
    ("gift_100_ring", "Uzuk", 100, 26000), ("gift_100_diamond", "Olmos", 100, 26000),
]

async def seed_catalog():
    async with Session.begin() as s:
        if not await s.get(Setting, "min_payment"):
            s.add(Setting(key="min_payment", value="2000"))
        existing = {x.code for x in (await s.scalars(select(Product))).all()}
        for code, name, months, price in PREMIUM:
            if code not in existing:
                s.add(Product(kind="premium", code=code, name_uz=name, name_ru=name,
                              duration_months=months, price=price))
        for qty, price in STARS:
            code = f"stars_{qty}"
            if code not in existing:
                s.add(Product(kind="stars", code=code, name_uz=f"{qty} Stars", name_ru=f"{qty} Stars",
                              quantity=qty, price=price))
        for code, name, stars, price in GIFTS:
            if code not in existing:
                s.add(Product(kind="gift", code=code, name_uz=f"{name} ({stars} ⭐)",
                              name_ru=f"{name} ({stars} ⭐)", quantity=stars, price=price))

async def sync_services():
    data = await api_services()
    async with Session.begin() as s:
        seen = set()
        for item in data:
            sid = str(item.get("service", ""))
            if not sid:
                continue
            seen.add(sid)
            obj = await s.scalar(select(Service).where(Service.provider_service_id == sid))
            rate = Decimal(str(item.get("rate", 0)))
            if not obj:
                obj = Service(provider_service_id=sid, name=str(item.get("name", "")),
                              category=str(item.get("category", "")), api_rate=rate,
                              min_qty=int(item.get("min", 0) or 0), max_qty=int(item.get("max", 0) or 0))
                s.add(obj)
            else:
                obj.name = str(item.get("name", obj.name))
                obj.category = str(item.get("category", obj.category or ""))
                obj.api_rate = rate
                obj.min_qty = int(item.get("min", obj.min_qty or 0) or 0)
                obj.max_qty = int(item.get("max", obj.max_qty or 0) or 0)
                obj.active = True
        for obj in (await s.scalars(select(Service))).all():
            if obj.provider_service_id not in seen:
                obj.active = False
