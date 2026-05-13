"""CLI entry point — `yt-research run --niche … --seed-channels …`."""

from __future__ import annotations

import logging
from pathlib import Path

import click
from dotenv import load_dotenv
from rich.console import Console
from rich.table import Table

from .pipeline import render_report, research_niche


console = Console()


@click.group()
def cli() -> None:
    """yt-research-agent — programmatic YouTube content research."""
    load_dotenv()
    logging.basicConfig(
        level=logging.WARNING,
        format="%(levelname)s %(name)s: %(message)s",
    )


@cli.command()
@click.option("--niche", required=True, help="Niche keyword, e.g. 'algorithmic trading'.")
@click.option("--seed-channels", default="",
              help="Comma-separated YouTube channel IDs (UC...) to anchor the search.")
@click.option("--subreddits", default="",
              help="Comma-separated subreddits to mine for community signals.")
@click.option("--top-n", default=5, show_default=True,
              help="Number of briefs to generate.")
@click.option("--output", default="output/briefs.md", show_default=True,
              type=click.Path(dir_okay=False, writable=True),
              help="Path to write the report.")
@click.option("-v", "--verbose", is_flag=True,
              help="Show INFO logs (sources tried, signals collected).")
def run(niche: str, seed_channels: str, subreddits: str,
        top_n: int, output: str, verbose: bool) -> None:
    """Run the full pipeline and write a markdown report."""
    if verbose:
        logging.getLogger().setLevel(logging.INFO)

    seeds = [s.strip() for s in seed_channels.split(",") if s.strip()]
    subs = [s.strip().lstrip("r/") for s in subreddits.split(",") if s.strip()]

    console.print(f"[bold cyan]niche:[/] {niche}")
    if seeds:
        console.print(f"[bold cyan]seed channels:[/] {', '.join(seeds)}")
    if subs:
        console.print(f"[bold cyan]subreddits:[/] {', '.join(subs)}")
    console.print(f"[bold cyan]top-n:[/] {top_n}")
    console.print()

    with console.status("[bold]Running pipeline…"):
        result = research_niche(
            niche=niche, seed_channels=seeds, subreddits=subs, top_n=top_n,
        )

    # Summary table
    table = Table(title=f"Signals collected — {niche}")
    table.add_column("Source", style="cyan")
    table.add_column("Count", justify="right")
    table.add_row("Videos", str(len(result.raw.videos)))
    table.add_row("Channels", str(len(result.raw.channels)))
    table.add_row("Outliers (>=10x)", str(len(result.outliers)))
    table.add_row("Trend signals", str(len(result.raw.trends)))
    table.add_row("Reddit signals", str(len(result.raw.reddit)))
    table.add_row("Ranked trends", str(len(result.ranked_trends)))
    table.add_row("Scored ideas (top-n)", str(len(result.scored_ideas)))
    table.add_row("Briefs generated", str(len(result.briefs)))
    console.print(table)
    console.print()

    # Brief summary
    brief_table = Table(title="Briefs by score")
    brief_table.add_column("#", justify="right")
    brief_table.add_column("Score", justify="right")
    brief_table.add_column("Topic")
    brief_table.add_column("Hook (truncated)")
    for i, b in enumerate(result.briefs, 1):
        brief_table.add_row(
            str(i), f"{b.scored_idea.total:.1f}",
            b.scored_idea.idea.topic[:50],
            (b.hook[:60] + "…") if len(b.hook) > 60 else b.hook,
        )
    console.print(brief_table)
    console.print()

    # Write the full report
    out_path = Path(output)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(render_report(result), encoding="utf-8")
    console.print(f"[bold green]Report written:[/] {out_path.resolve()}")


def main() -> None:
    cli()


if __name__ == "__main__":
    main()
