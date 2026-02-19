#!/usr/bin/env python3
"""Initialize the database schema."""
import asyncio
import sys

sys.path.insert(0, ".")

from app.db import get_db, init_schema


async def main():
    conn = await get_db()
    try:
        await init_schema(conn)
        print("Database initialized.")
    finally:
        await conn.close()


if __name__ == "__main__":
    asyncio.run(main())
