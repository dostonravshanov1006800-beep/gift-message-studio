"""Запускает сервер Mini App и бота в одном процессе. Любой сбой -> автоперезапуск (24/7)."""
import asyncio
import logging
import os

import uvicorn

from bot import run_bot
from server import app

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
log = logging.getLogger("gms")


async def keep_alive(name, factory):
    """Перезапускает корутину после любой ошибки, с растущей паузой (до 60 с)."""
    delay = 2
    while True:
        started = asyncio.get_event_loop().time()
        try:
            await factory()
            log.warning("%s завершился сам, перезапуск", name)
        except asyncio.CancelledError:
            raise
        except Exception:
            log.exception("%s упал, перезапуск через %s с", name, delay)
        if asyncio.get_event_loop().time() - started > 120:
            delay = 2  # работал долго — сбрасываем паузу
        await asyncio.sleep(delay)
        delay = min(delay * 2, 60)


async def serve_web():
    cfg = uvicorn.Config(app, host="0.0.0.0", port=int(os.environ.get("PORT", 8080)), log_level="info")
    await uvicorn.Server(cfg).serve()


async def main():
    await asyncio.gather(keep_alive("web", serve_web), keep_alive("bot", run_bot))


if __name__ == "__main__":
    asyncio.run(main())
