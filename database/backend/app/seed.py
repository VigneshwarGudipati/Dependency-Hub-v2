"""CLI script to seed default database reference data."""

import asyncio
from app.core.database import AsyncSessionLocal
from app.core.seeds import seed_reference_data


async def main() -> None:
    print("Seeding Dependency Hub reference data (roles, permissions, ecosystems, licenses)...")
    async with AsyncSessionLocal() as session:
        counts = await seed_reference_data(session)
        print(f"Seeding completed successfully: {counts}")


if __name__ == "__main__":
    asyncio.run(main())
