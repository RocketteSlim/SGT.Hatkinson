import sqlite3
import os
import shutil
from datetime import datetime

def backup_database(db_path, backup_path):
    """Create a backup of the database."""
    try:
        shutil.copy2(db_path, backup_path)
        print(f"Backup created at: {backup_path}")
    except Exception as e:
        print(f"Error creating backup: {e}")
        raise

def inspect_table(db_path):
    """Inspect the important_messages table and return rows."""
    try:
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        cursor.execute("""
            SELECT id, title, content, interval_seconds, typeof(interval_seconds)
            FROM important_messages
        """)
        rows = cursor.fetchall()
        print("\nCurrent data in important_messages:")
        print("ID | Title | Content | Interval_Seconds | Type")
        print("-" * 80)
        for row in rows:
            print(f"{row[0]} | {row[1]} | {row[2]} | {row[3]} | {row[4]}")
        conn.close()
        return rows
    except Exception as e:
        print(f"Error inspecting table: {e}")
        raise

def fix_invalid_interval(db_path):
    """Update invalid interval_seconds to 600."""
    try:
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        cursor.execute("""
            UPDATE important_messages
            SET interval_seconds = 600
            WHERE interval_seconds = 'Test message rémanent'
        """)
        conn.commit()
        updated_rows = cursor.rowcount
        print(f"\nUpdated {updated_rows} row(s) with interval_seconds = 'Test message rémanent' to 600")
        conn.close()
    except Exception as e:
        print(f"Error fixing invalid intervals: {e}")
        raise

def main():
    db_path = r"C:\Users\Shadow\Desktop\discord_bot 3\embeds.db"
    backup_path = rf"C:\Users\Shadow\Desktop\discord_bot 3\embeds_{datetime.now().strftime('%Y%m%d_%H%M%S')}.bak"

    # Verify database exists
    if not os.path.exists(db_path):
        print(f"Error: Database not found at {db_path}")
        return

    # Create backup
    backup_database(db_path, backup_path)

    # Inspect table before fix
    inspect_table(db_path)

    # Fix invalid interval_seconds
    fix_invalid_interval(db_path)

    # Inspect table after fix
    inspect_table(db_path)

    print("\nDatabase fix completed. You can now restart the bot.")

if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        print(f"Script failed: {e}")