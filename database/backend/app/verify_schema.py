"""Schema verification script."""

import asyncio
from sqlalchemy import text
from app.core.database import engine


async def verify() -> None:
    async with engine.connect() as conn:
        res = await conn.execute(text("""
            SELECT table_name 
            FROM information_schema.tables 
            WHERE table_schema = 'public' 
            ORDER BY table_name;
        """))
        tables = [r[0] for r in res.fetchall()]
        print(f"Total tables: {len(tables)}")
        for t in tables:
            print(f" - {t}")


if __name__ == "__main__":
    asyncio.run(verify())
