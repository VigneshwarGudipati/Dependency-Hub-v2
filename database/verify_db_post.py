import asyncio
import asyncpg
from app.core.config import settings

async def verify_post_migration():
    try:
        conn = await asyncpg.connect(settings.async_database_url.replace("postgresql+asyncpg://", "postgresql://"))
        
        # Check tables
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
        
        # Check constraints (Foreign Keys, Unique, Check)
        constraints = await conn.fetch('''
            SELECT constraint_type, count(*) 
            FROM information_schema.table_constraints 
            WHERE table_schema = 'public'
            GROUP BY constraint_type
        ''')
        for c in constraints:
            print(f"{c['constraint_type']}: {c['count']}")
            
        # Check indexes
        indexes = await conn.fetch('''
            SELECT count(*) 
            FROM pg_indexes 
            WHERE schemaname = 'public'
        ''')
        print(f"INDEXES: {indexes[0]['count']}")

        # Check Enums
        enums = await conn.fetch('''
            SELECT count(*)
            FROM pg_type t 
            JOIN pg_enum e on t.oid = e.enumtypid  
            JOIN pg_catalog.pg_namespace n ON n.oid = t.typnamespace
            WHERE n.nspname = 'public'
        ''')
        print(f"ENUM TYPES (values): {enums[0]['count']}")
            
        if len(domain_tables) == 23 and alembic_exists:
            print("Post-migration verification PASSED.")
        else:
            print("Post-migration verification FAILED: Table count mismatch.")
            
        await conn.close()
        
    except Exception as e:
        print(f"Error connecting to database: {e}")

if __name__ == "__main__":
    asyncio.run(verify_post_migration())
