from apscheduler.triggers.cron import CronTrigger
from database import DB_PATH
import aiosqlite
from datetime import datetime, timedelta

async def send_reminders(bot):
    now = datetime.now()
    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute('''
            SELECT t.id, t.description, t.end_date, t.status, u.tg_user_id
            FROM tasks t
            JOIN users u ON t.user_id = u.id
            WHERE t.next_reminder <= ? AND t.status != 'готово'
        ''', (now.strftime("%Y-%m-%d %H:%M:%S"),)) as cursor:
            rows = await cursor.fetchall()
        for row in rows:
            task_id, desc, end_date, status, tg_id = row
            try:
                await bot.send_message(
                    tg_id,
                    f"🔔 <b>Напоминание о практике</b>\\n\\n"
                    f"Описание: {desc}\\n"
                    f"Срок: {end_date}\\n\\n"
                    f"Напоминание повторяется еженедельно, пока задача не будет отмечена как «готово».",
                    parse_mode="HTML"
                )
                next_rem = now + timedelta(weeks=1)
                await db.execute(
                    "UPDATE tasks SET next_reminder = ? WHERE id = ?",
                    (next_rem.strftime("%Y-%m-%d %H:%M:%S"), task_id)
                )
            except Exception as e:
                print(f"Не удалось отправить напоминание пользователю {tg_id}: {e}")
        await db.commit()

def setup_scheduler(scheduler, bot):
    scheduler.add_job(
        send_reminders,
        CronTrigger(hour=9, minute=0),
        args=[bot],
        id="daily_reminders",
        replace_existing=True
    )
