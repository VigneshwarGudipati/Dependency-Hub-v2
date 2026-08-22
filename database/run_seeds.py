import asyncio
from app.core.database import AsyncSessionLocal
from app.core.seeds import seed_reference_data

async def run_seed_test():
    print("--- FIRST SEED RUN ---")
    async with AsyncSessionLocal() as session:
        result1 = await seed_reference_data(session)
        print(f"Seed 1 inserted: {result1}")
        
    print("\n--- SECOND SEED RUN ---")
    async with AsyncSessionLocal() as session:
        result2 = await seed_reference_data(session)
        print(f"Seed 2 inserted: {result2}")
        
    idempotent = all(v == 0 for v in result2.values())
    print(f"\nIdempotent: {idempotent}")

if __name__ == "__main__":
    asyncio.run(run_seed_test())
