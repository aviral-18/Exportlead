"""
Database initialisation script.
Run once after first `docker compose up`:
    python scripts/init_db.py

Steps:
  1. Run Alembic migrations (creates all tables + partitions + indexes)
  2. Verify extensions exist
  3. Print summary
"""
from __future__ import annotations

import asyncio
import subprocess
import sys
from pathlib import Path

import asyncpg
from rich.console import Console
from rich.table import Table

console = Console()

PROJECT_ROOT = Path(__file__).parent.parent


def run_migrations() -> bool:
    console.print("[bold blue]Running Alembic migrations...[/bold blue]")
    result = subprocess.run(
        [sys.executable, "-m", "alembic", "upgrade", "head"],
        cwd=PROJECT_ROOT,
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        console.print(f"[red]Migration failed:[/red]\n{result.stderr}")
        return False
    console.print(f"[green]✓ Migrations complete[/green]\n{result.stdout}")
    return True


async def verify_db() -> None:
    from src.core.config import settings

    # Strip async driver prefix for asyncpg
    dsn = settings.database_url.replace("postgresql+asyncpg://", "postgresql://")

    conn = await asyncpg.connect(dsn)
    try:
        # Check extensions
        console.print("\n[bold]Checking PostgreSQL extensions:[/bold]")
        exts = await conn.fetch(
            "SELECT extname, extversion FROM pg_extension ORDER BY extname"
        )
        tbl = Table("Extension", "Version")
        for ext in exts:
            tbl.add_row(ext["extname"], ext["extversion"])
        console.print(tbl)

        # Check tables
        console.print("\n[bold]Tables created:[/bold]")
        tables = await conn.fetch(
            """
            SELECT tablename, pg_size_pretty(pg_total_relation_size(quote_ident(tablename))) AS size
            FROM pg_tables
            WHERE schemaname = 'public'
            ORDER BY tablename
            """
        )
        tbl2 = Table("Table", "Size")
        for t in tables:
            tbl2.add_row(t["tablename"], t["size"])
        console.print(tbl2)

        # Check partitions
        part_count = await conn.fetchval(
            "SELECT COUNT(*) FROM pg_tables WHERE tablename LIKE 'raw_buyers_p%'"
        )
        console.print(f"\n[green]✓ {part_count} raw_buyers partitions created[/green]")

        # Check indexes
        idx_count = await conn.fetchval(
            "SELECT COUNT(*) FROM pg_indexes WHERE schemaname = 'public'"
        )
        console.print(f"[green]✓ {idx_count} indexes created[/green]")

    finally:
        await conn.close()


if __name__ == "__main__":
    console.print("[bold green]BrassExport Intelligence — Database Init[/bold green]")

    if not run_migrations():
        sys.exit(1)

    asyncio.run(verify_db())
    console.print("\n[bold green]✓ Database ready![/bold green]")
    console.print("\nNext steps:")
    console.print("  1. Copy .env.example to .env and fill in API keys")
    console.print("  2. Start workers: docker compose up worker-ingest worker-pipeline")
    console.print("  3. Trigger scrapers: POST /api/v1/pipeline/trigger-full")
    console.print("  4. Monitor at: http://localhost:5555 (Flower)")
    console.print("  5. API docs at:  http://localhost:8000/docs")
