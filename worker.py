"""Воркер для GitHub Actions: слушает Telegram WORKER_SECONDS секунд (long polling) и отвечает.
Обновления подтверждаются offset-ом внутри Telegram, поэтому следующий воркер ничего не пропустит и не продублирует."""
import asyncio
import logging
import os
import time

from aiogram.types import Update

import bot as botmod

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
log = logging.getLogger("worker")


async def main():
    deadline = time.time() + int(os.environ.get("WORKER_SECONDS", "330"))
    bot, dp = botmod.bot, botmod.dp
    await bot.delete_webhook(drop_pending_updates=False)
    try:
        await botmod.setup_menu()
    except Exception:
        log.exception("menu setup failed")
    offset = None
    handled = 0
    while time.time() < deadline:
        left = int(deadline - time.time())
        try:
            updates = await bot.get_updates(offset=offset, timeout=min(25, max(1, left)),
                                            allowed_updates=["message", "callback_query"])
        except Exception:
            log.exception("get_updates failed")
            await asyncio.sleep(2)
            continue
        for u in updates:
            offset = u.update_id + 1
            try:
                await dp.feed_update(bot, u)
                handled += 1
            except Exception:
                log.exception("update %s failed", u.update_id)
    if offset:  # подтверждаем обработанное, чтобы следующий воркер не повторил
        await bot.get_updates(offset=offset, timeout=0)
    log.info("worker done, handled %s updates", handled)
    await bot.session.close()


if __name__ == "__main__":
    asyncio.run(main())
