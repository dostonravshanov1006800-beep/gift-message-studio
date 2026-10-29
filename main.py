"""Запускает сервер Mini App и бота в одном процессе."""
import asyncio
import os

import uvicorn

from bot import run_bot
from server import app


async def main():
    cfg = uvicorn.Config(app, host="0.0.0.0", port=int(os.environ.get("PORT", 8080)), log_level="info")
    server = uvicorn.Server(cfg)
    await asyncio.gather(server.serve(), run_bot())


if __name__ == "__main__":
    asyncio.run(main())
