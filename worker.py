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


async def spawn_successor():
    """За ~110 с до конца запускаем следующий воркер: пока он ставит пакеты, этот ещё отвечает (без дыры в 24/7).
    concurrency держит его в очереди, поэтому два воркера одновременно не опрашивают Telegram."""
    tok, repo, ref = os.environ.get("GH_TOKEN"), os.environ.get("GH_REPO"), os.environ.get("GH_REF", "main")
    if not (tok and repo):
        return
    import httpx
    try:
        async with httpx.AsyncClient(timeout=15) as c:
            r = await c.post(f"https://api.github.com/repos/{repo}/actions/workflows/bot.yml/dispatches",
                             headers={"Authorization": f"Bearer {tok}", "Accept": "application/vnd.github+json"},
                             json={"ref": ref})
        log.info("successor dispatch: HTTP %s", r.status_code)
    except Exception:
        log.exception("successor dispatch failed (cron подхватит)")


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
    spawned = False
    while time.time() < deadline:
        if not spawned and deadline - time.time() < 110:
            spawned = True
            asyncio.create_task(spawn_successor())
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
