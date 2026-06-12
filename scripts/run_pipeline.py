"""
CLI to manually trigger pipeline stages.
Usage:
    python scripts/run_pipeline.py scrape --source volza
    python scripts/run_pipeline.py scrape --all-public
    python scripts/run_pipeline.py dedup
    python scripts/run_pipeline.py resolve
    python scripts/run_pipeline.py full
"""
from __future__ import annotations

import asyncio
import sys
from pathlib import Path

import click
from rich.console import Console
from rich.progress import Progress, SpinnerColumn, TextColumn

PROJECT_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

console = Console()

SCRAPER_MAP = {
    "volza":             "src.scrapers.trade_intelligence.volza.VolzaScraper",
    "import_yeti":       "src.scrapers.trade_intelligence.import_yeti.ImportYetiScraper",
    "un_comtrade":       "src.scrapers.trade_intelligence.un_comtrade.UnComtradeScraper",
    "trade_map":         "src.scrapers.trade_intelligence.trade_map.TradeMapScraper",
    "export_genius":     "src.scrapers.trade_intelligence.export_genius.ExportGeniusScraper",
    "datamyne":          "src.scrapers.trade_intelligence.datamyne.DatamyneScraper",
    "panjiva":           "src.scrapers.trade_intelligence.panjiva.PanjivaScraper",
    "india_export_data": "src.scrapers.trade_intelligence.india_export_data.IndiaExportDataScraper",
    "alibaba":           "src.scrapers.b2b_marketplaces.alibaba.AlibabaScraper",
    "global_sources":    "src.scrapers.b2b_marketplaces.global_sources.GlobalSourcesScraper",
    "tradekey":          "src.scrapers.b2b_marketplaces.tradekey.TradeKeyScraper",
    "ec21":              "src.scrapers.b2b_marketplaces.ec21.EC21Scraper",
    "eworldtrade":       "src.scrapers.b2b_marketplaces.eworldtrade.EWorldTradeScraper",
    "tradeindia":        "src.scrapers.b2b_marketplaces.tradeindia.TradeIndiaScraper",
    "indiamart":         "src.scrapers.b2b_marketplaces.indiamart.IndiaMARTScraper",
    "made_in_china":     "src.scrapers.b2b_marketplaces.made_in_china.MadeInChinaScraper",
    "sam_gov":           "src.scrapers.procurement.sam_gov.SamGovScraper",
    "ted_europa":        "src.scrapers.procurement.ted_europa.TEDEuropaScraper",
    "ungm":              "src.scrapers.procurement.ungm.UNGMScraper",
    "world_bank":        "src.scrapers.procurement.world_bank.WorldBankScraper",
    "adb":               "src.scrapers.procurement.adb.ADBScraper",
    "ambiente":          "src.scrapers.trade_fairs.ambiente.AmbienteScraper",
    "maison_objet":      "src.scrapers.trade_fairs.maison_objet.MaisonObjetScraper",
    "ny_now":            "src.scrapers.trade_fairs.ny_now.NYNowScraper",
    "ihgf":              "src.scrapers.trade_fairs.ihgf.IHGFFairScraper",
}

PUBLIC_SCRAPERS = [
    "un_comtrade", "sam_gov", "world_bank", "adb", "ungm",
    "ted_europa", "india_export_data",
]


@click.group()
def cli():
    """BrassExport Intelligence pipeline CLI."""


@cli.command()
@click.option("--source", "-s", multiple=True, help="Scraper name(s)")
@click.option("--all-public", is_flag=True, help="Run all public/free scrapers")
@click.option("--all", "run_all", is_flag=True, help="Run all scrapers")
def scrape(source, all_public, run_all):
    """Run one or more scrapers."""
    if run_all:
        sources = list(SCRAPER_MAP.keys())
    elif all_public:
        sources = PUBLIC_SCRAPERS
    elif source:
        sources = list(source)
    else:
        console.print("[red]Specify --source, --all-public, or --all[/red]")
        sys.exit(1)

    from src.pipeline.ingestion import run_scraper
    from importlib import import_module

    async def _run():
        total = 0
        for name in sources:
            path = SCRAPER_MAP.get(name, name)
            parts = path.rsplit(".", 1)
            try:
                mod = import_module(parts[0])
                cls = getattr(mod, parts[1])
            except (ImportError, AttributeError) as e:
                console.print(f"[red]Cannot load {name}: {e}[/red]")
                continue

            with Progress(SpinnerColumn(), TextColumn(f"[cyan]Scraping {name}...")) as prog:
                t = prog.add_task(name)
                count = await run_scraper(cls)
                total += count
                console.print(f"  [green]✓ {name}: {count} records[/green]")
        console.print(f"\n[bold green]Total: {total} records ingested[/bold green]")

    asyncio.run(_run())


@cli.command()
@click.option("--min-score", default=0.70, show_default=True)
def dedup(min_score):
    """Run deduplication pipeline."""
    from src.pipeline.deduplication import domain_exact_dedup, find_duplicate_candidates

    async def _run():
        console.print("[cyan]Running domain-exact dedup...[/cyan]")
        n1 = await domain_exact_dedup()
        console.print(f"  [green]✓ {n1} domain-exact pairs[/green]")

        console.print("[cyan]Running MinHash LSH dedup...[/cyan]")
        n2 = await find_duplicate_candidates(min_score=min_score)
        console.print(f"  [green]✓ {n2} LSH candidate pairs[/green]")

    asyncio.run(_run())


@cli.command()
@click.option("--threshold", default=0.85, show_default=True)
def resolve(threshold):
    """Run entity resolution (Union-Find clustering)."""
    from src.pipeline.entity_resolution import resolve_entities

    async def _run():
        console.print("[cyan]Resolving entities...[/cyan]")
        n = await resolve_entities(score_threshold=threshold)
        console.print(f"  [green]✓ {n} canonical records created/updated[/green]")

    asyncio.run(_run())


@cli.command()
def full():
    """Run full pipeline: all scrapers → dedup → entity resolution."""
    ctx = click.get_current_context()
    ctx.invoke(scrape, all_public=True)
    ctx.invoke(dedup)
    ctx.invoke(resolve)
    console.print("\n[bold green]Full pipeline complete![/bold green]")


if __name__ == "__main__":
    cli()
