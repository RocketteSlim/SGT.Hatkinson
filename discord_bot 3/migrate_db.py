import aiosqlite
import asyncio

async def migrate_db():
    async with aiosqlite.connect("embeds.db") as db:
        try:
            # Check if 'paused' column exists
            cursor = await db.execute("PRAGMA table_info(important_messages)")
            columns = await cursor.fetchall()
            column_names = [col[1] for col in columns]
            
            if "paused" not in column_names:
                await db.execute("ALTER TABLE important_messages ADD COLUMN paused BOOLEAN DEFAULT FALSE")
                await db.commit()
                print("Database migration successful: Added 'paused' column to important_messages")
            else:
                print("Migration not needed: 'paused' column already exists")
        except Exception as e:
            print(f"Error during migration: {e}")
            raise

if __name__ == "__main__":
    asyncio.run(migrate_db())