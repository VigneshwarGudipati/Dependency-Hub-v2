import asyncio
import asyncpg
from app.core.config import settings

async def verify_pre_migration():
    print(f"Connecting to database: {settings.POSTGRES_DB}")
    print(f"Host: {settings.POSTGRES_HOST}, Port: {settings.POSTGRES_PORT}")
    
    try:
        conn = await asyncpg.connect(settings.async_database_url.replace("postgresql+asyncpg://", "postgresql://"))
        
        # Check current domain tables
        tables = await conn.fetch('''
            SELECT table_name 
            FROM information_schema.tables 
            WHERE table_schema = 'public' AND table_type = 'BASE TABLE'
        ''')
        
        table_names = [t['table_name'] for t in tables]
        domain_tables = [t for t in table_names if t != 'alembic_version']
        alembic_exists = 'alembic_version' in table_names
        
        print(f"Current domain tables count: {len(domain_tables)}")
        print(f"alembic_version exists: {alembic_exists}")
        
        if len(domain_tables) == 0 and not alembic_exists:
            print("Pre-migration verification PASSED.")
        else:
            print("Pre-migration verification FAILED: Tables exist.")
            
        await conn.close()
        
    except Exception as e:
        print(f"Error connecting to database: {e}")

if __name__ == "__main__":
    asyncio.run(verify_pre_migration())
