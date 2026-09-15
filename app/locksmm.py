import httpx
from .config import settings

class LocksmmError(Exception):
    pass

async def call(params: dict):
    if not settings.locksmm_api_key:
        raise LocksmmError("LOCKSMM_API_KEY not configured")
    payload = dict(params)
    payload["key"] = settings.locksmm_api_key
    last = None
    async with httpx.AsyncClient(timeout=30) as client:
        for attempt in range(3):
            try:
                r = await client.post(settings.locksmm_api_url, data=payload)
                r.raise_for_status()
                data = r.json()
                if isinstance(data, dict) and data.get("error"):
                    raise LocksmmError(str(data["error"]))
                return data
            except LocksmmError:
                raise
            except (httpx.HTTPError, ValueError) as exc:
                last = exc
                if attempt < 2:
                    continue
    raise LocksmmError(str(last or "API request failed"))

async def balance(): return await call({"action":"balance"})
async def services(): return await call({"action":"services"})
async def add(service, link, quantity): return await call({"action":"add","service":service,"link":link,"quantity":quantity})
async def status(order=None, orders=None):
    p = {"action":"status"}
    if order is not None: p["order"] = order
    if orders is not None: p["orders"] = orders
    return await call(p)
async def orders(limit=100, offset=0): return await call({"action":"orders","limit":limit,"offset":offset})
