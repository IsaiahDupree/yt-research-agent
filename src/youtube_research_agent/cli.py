"""CLI entry point — `yt-research run --niche … --seed-channels …`."""

from __future__ import annotations

import logging
import os
import re
from datetime import datetime, timezone
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


# ---------------------------------------------------------------------------
# report — same as run, but auto-dates the filename when --output is a dir.
# Used by the weekly GitHub Action.
# ---------------------------------------------------------------------------


@cli.command()
@click.option("--niche", required=True)
@click.option("--seed-channels", default="")
@click.option("--subreddits", default="")
@click.option("--top-n", default=5, show_default=True)
@click.option("--output", default="reports/weekly", show_default=True,
              type=click.Path(file_okay=True, dir_okay=True, writable=True),
              help="Output path. If a directory, the filename will be "
                   "auto-dated as <YYYY-MM-DD>.md.")
@click.option("--demo", "use_demo", is_flag=True,
              help="Seed the cache with built-in algo-trading fixtures.")
def report(niche: str, seed_channels: str, subreddits: str,
           top_n: int, output: str, use_demo: bool) -> None:
    """Run the pipeline and write a dated weekly report.

    Designed for unattended use (CI / cron). Auto-dates the output
    filename when --output is a directory.
    """
    seeds = [s.strip() for s in seed_channels.split(",") if s.strip()]
    subs = [s.strip().lstrip("r/") for s in subreddits.split(",") if s.strip()]

    if use_demo:
        from .demo_fixtures import SEED_CHANNELS as DEMO_SEEDS, seed_demo_cache
        cache_dir = Path(os.environ.get("YTR_CACHE_DIR", ".cache"))
        cache_dir.mkdir(parents=True, exist_ok=True)
        seed_demo_cache(cache_dir)
        if not seeds:
            seeds = list(DEMO_SEEDS)
        if not subs:
            subs = ["algotrading"]

    result = research_niche(
        niche=niche, seed_channels=seeds, subreddits=subs, top_n=top_n,
    )

    out_path = Path(output)
    if out_path.is_dir() or output.endswith("/") or output.endswith(os.sep):
        date = datetime.now(timezone.utc).strftime("%Y-%m-%d")
        out_path = out_path / f"{date}.md"
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(render_report(result), encoding="utf-8")
    click.echo(f"Report written: {out_path}")
    click.echo(
        f"Signals: videos={len(result.raw.videos)} "
        f"channels={len(result.raw.channels)} "
        f"outliers={len(result.outliers)} "
        f"trends={len(result.raw.trends)} "
        f"reddit={len(result.raw.reddit)} "
        f"briefs={len(result.briefs)}"
    )


# ---------------------------------------------------------------------------
# diff — week-over-week change summary
# ---------------------------------------------------------------------------


# Parse the outlier rows out of a report's "### Top outliers" table.
# Row format: "| 23.8× | Title | Channel | 1,240,000 |"
_OUTLIER_ROW = re.compile(
    r"^\|\s*([\d.]+×|∞)\s*\|\s*([^|]+?)\s*\|\s*([^|]+?)\s*\|\s*([\d,]+)\s*\|"
)

# Parse ranked-signal rows. Format: "| 0.360 | reddit | query | 1.00 |"
_SIGNAL_ROW = re.compile(
    r"^\|\s*([\d.]+)\s*\|\s*(\w+)\s*\|\s*([^|]+?)\s*\|\s*([\d.]+)\s*\|"
)


def parse_outliers(markdown: str) -> list[dict]:
    """Extract outlier rows from a rendered report."""
    rows = []
    in_table = False
    for line in markdown.splitlines():
        if line.startswith("### Top outliers"):
            in_table = True
            continue
        if in_table and line.startswith("### "):
            break
        if not in_table:
            continue
        m = _OUTLIER_ROW.match(line)
        if not m:
            continue
        rows.append({
            "multiplier": m.group(1),
            "title": m.group(2).strip(),
            "channel": m.group(3).strip(),
            "views": m.group(4).strip(),
        })
    return rows


def parse_signals(markdown: str) -> list[dict]:
    """Extract ranked-signal rows from a rendered report."""
    rows = []
    in_table = False
    for line in markdown.splitlines():
        if line.startswith("### Top ranked signals"):
            in_table = True
            continue
        if in_table and (line.startswith("### ") or line.startswith("---")):
            break
        if not in_table:
            continue
        m = _SIGNAL_ROW.match(line)
        if not m:
            continue
        rows.append({
            "composite": m.group(1),
            "source": m.group(2),
            "query": m.group(3).strip(),
            "velocity": m.group(4),
        })
    return rows


def render_diff(old_md: str, new_md: str) -> str:
    """Compose a markdown summary of week-over-week change."""
    old_o = parse_outliers(old_md)
    new_o = parse_outliers(new_md)
    old_s = parse_signals(old_md)
    new_s = parse_signals(new_md)

    old_outlier_titles = {o["title"] for o in old_o}
    new_outlier_titles = {o["title"] for o in new_o}
    fresh = [o for o in new_o if o["title"] not in old_outlier_titles]
    dropped = [o for o in old_o if o["title"] not in new_outlier_titles]

    old_signal_queries = {s["query"] for s in old_s}
    new_signal_queries = {s["query"] for s in new_s}
    fresh_signals = [s for s in new_s if s["query"] not in old_signal_queries]
    dropped_signals = [s for s in old_s if s["query"] not in new_signal_queries]

    lines: list[str] = ["# Week-over-week diff", ""]

    lines.append(f"## New outliers ({len(fresh)})")
    lines.append("")
    if fresh:
        lines.append("| Multiplier | Title | Channel |")
        lines.append("|---|---|---|")
        for o in fresh:
            lines.append(f"| {o['multiplier']} | {o['title']} | {o['channel']} |")
    else:
        lines.append("_No new outliers._")
    lines.append("")

    lines.append(f"## Dropped outliers ({len(dropped)})")
    lines.append("")
    if dropped:
        lines.append("| Multiplier | Title | Channel |")
        lines.append("|---|---|---|")
        for o in dropped:
            lines.append(f"| {o['multiplier']} | {o['title']} | {o['channel']} |")
    else:
        lines.append("_No drops since last week._")
    lines.append("")

    lines.append(f"## New ranked signals ({len(fresh_signals)})")
    lines.append("")
    if fresh_signals:
        lines.append("| Composite | Source | Query |")
        lines.append("|---|---|---|")
        for s in fresh_signals:
            lines.append(f"| {s['composite']} | {s['source']} | {s['query']} |")
    else:
        lines.append("_No new signals._")
    lines.append("")

    lines.append(f"## Dropped signals ({len(dropped_signals)})")
    lines.append("")
    if dropped_signals:
        lines.append("| Composite | Source | Query |")
        lines.append("|---|---|---|")
        for s in dropped_signals:
            lines.append(f"| {s['composite']} | {s['source']} | {s['query']} |")
    else:
        lines.append("_No drops since last week._")
    lines.append("")

    return "\n".join(lines)


@cli.command()
@click.argument("old_path", type=click.Path(exists=True, dir_okay=False, readable=True))
@click.argument("new_path", type=click.Path(exists=True, dir_okay=False, readable=True))
@click.option("--output", default="-",
              help="Where to write the diff. '-' (default) writes to stdout.")
def diff(old_path: str, new_path: str, output: str) -> None:
    """Compare two reports and write a markdown change summary."""
    old_md = Path(old_path).read_text(encoding="utf-8")
    new_md = Path(new_path).read_text(encoding="utf-8")
    out = render_diff(old_md, new_md)
    if output == "-":
        click.echo(out)
    else:
        Path(output).parent.mkdir(parents=True, exist_ok=True)
        Path(output).write_text(out, encoding="utf-8")
        click.echo(f"Diff written: {output}")


def main() -> None:
    cli()


if __name__ == "__main__":
    main()
