import aiosqlite
import discord
from datetime import datetime
import datetime as dt

async def init_db():
    async with aiosqlite.connect("embeds.db") as db:
        await db.execute("""
            CREATE TABLE IF NOT EXISTS important_messages (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                title TEXT,
                content TEXT,
                channel_id INTEGER,
                interval_seconds INTEGER,
                user_id INTEGER,
                image_url TEXT,
                paused BOOLEAN,
                message_id INTEGER,
                created_at TEXT
            )
        """)
        await db.execute("""
            CREATE TABLE IF NOT EXISTS webhook_data (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                base_principale TEXT,
                objectifs TEXT,
                created_at TEXT
            )
        """)
        await db.commit()
    print("Database initialized successfully")

async def fetch_active_messages():
    try:
        async with aiosqlite.connect("embeds.db") as db:
            cursor = await db.execute("""
                SELECT id, title, content, channel_id, interval_seconds, user_id, image_url, paused, message_id, created_at
                FROM important_messages
            """)
            messages = await cursor.fetchall()
            return [
                {
                    "id": row[0],
                    "title": row[1],
                    "content": row[2],
                    "channel_id": row[3],
                    "interval_seconds": row[4],
                    "user_id": row[5],
                    "image_url": row[6],
                    "paused": bool(row[7]),
                    "message_id": row[8],
                    "created_at": row[9]
                } for row in messages
            ]
    except Exception as e:
        print(f"Error in fetch_active_messages: {e}")
        return []

async def fetch_latest_webhook_data():
    try:
        async with aiosqlite.connect("embeds.db") as db:
            cursor = await db.execute("SELECT base_principale, objectifs FROM webhook_data ORDER BY created_at DESC LIMIT 1")
            result = await cursor.fetchone()
            if result:
                return result[0], result[1]
            return None, None
    except Exception as e:
        print(f"Error in fetch_latest_webhook_data: {e}")
        return None, None