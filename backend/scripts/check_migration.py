#!/usr/bin/env python
"""Check if jti column exists in user_refresh_tokens table."""

import asyncio
import os
from sqlalchemy import text, inspect
from sqlalchemy.ext.asyncio import create_async_engine

async def check_jti_column():
    """Check if jti column exists."""
    database_url = os.getenv("DATABASE_URL", "postgresql+asyncpg://user:password@localhost/sentinel")
    
    engine = create_async_engine(database_url, echo=False)
    
    try:
        async with engine.connect() as conn:
            # Check if jti column exists
            result = await conn.execute(text("""
                SELECT column_name
                FROM information_schema.columns
                WHERE table_name = 'user_refresh_tokens'
                AND column_name = 'jti'
            """))
            row = result.fetchone()
            if row:
                print("✅ jti column EXISTS in user_refresh_tokens")
                return True
            else:
                print("❌ jti column DOES NOT EXIST in user_refresh_tokens")
                # List all columns
                result = await conn.execute(text("""
                    SELECT column_name
                    FROM information_schema.columns
                    WHERE table_name = 'user_refresh_tokens'
                    ORDER BY ordinal_position
                """))
                rows = result.fetchall()
                print("\nCurrent columns:")
                for r in rows:
                    print(f"  - {r[0]}")
                return False
    finally:
        await engine.dispose()

if __name__ == "__main__":
    result = asyncio.run(check_jti_column())
    exit(0 if result else 1)
