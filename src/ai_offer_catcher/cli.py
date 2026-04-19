from __future__ import annotations

import asyncio
import logging
from pathlib import Path

import typer

from ai_offer_catcher.app_settings import AppSettings
from ai_offer_catcher.artifacts import ArtifactStore
from ai_offer_catcher.db.connection import Database
from ai_offer_catcher.db.repository import Repository
from ai_offer_catcher.logging_utils import setup_logging
from ai_offer_catcher.reports.generate import generate_report
from ai_offer_catcher.utils import parse_cli_datetime

app = typer.Typer(help="Xiaohongshu AI Agent interview question MVP")
pipeline_app = typer.Typer(help="Pipeline commands")
app.add_typer(pipeline_app, name="pipeline")


def _build_repo() -> tuple[AppSettings, Repository]:
    setup_logging(logging.INFO)
    settings = AppSettings.load()
    repo = Repository(Database(settings.db_dsn))
    return settings, repo


def _load_keywords(settings: AppSettings) -> list[str]:
    return [line.strip() for line in settings.keywords_file.read_text(encoding="utf-8").splitlines() if line.strip()]


@app.command("init-db")
def init_db(sql_path: str = typer.Option("sql/init.sql", help="Path to init SQL")) -> None:
    settings, _ = _build_repo()
    Database(settings.db_dsn).init_db(Path(sql_path))
    typer.echo("Database initialized.")


@app.command("crawl-xhs")
def crawl_xhs(
    job_name: str = typer.Option(..., help="Logical crawl job name"),
    keywords_file: str | None = typer.Option(None, help="Optional keywords file"),
    max_pages: int = typer.Option(200, help="Max pages per keyword"),
    date_from: str | None = typer.Option(None, help="Inclusive start date, e.g. 2025-01-20"),
    date_to: str | None = typer.Option(None, help="Inclusive end date; omit to crawl until now"),
) -> None:
    from ai_offer_catcher.crawler.xhs_crawler import crawl_xiaohongshu

    settings, repo = _build_repo()
    keywords = _load_keywords(settings)
    if keywords_file:
        keywords = [line.strip() for line in Path(keywords_file).read_text(encoding="utf-8").splitlines() if line.strip()]
    artifacts = ArtifactStore(settings.artifact_root)
    asyncio.run(
        crawl_xiaohongshu(
            settings,
            repo,
            artifacts,
            job_name,
            keywords,
            max_pages,
            date_from=parse_cli_datetime(date_from),
            date_to=parse_cli_datetime(date_to),
        )
    )
    typer.echo("Crawl finished.")


@app.command("classify-posts")
def classify_posts(limit: int = typer.Option(50, help="Max posts to process")) -> None:
    from ai_offer_catcher.pipeline import PipelineRunner

    settings, repo = _build_repo()
    processed = PipelineRunner(settings, repo).classify_posts(limit)
    typer.echo(f"Classified {processed} posts.")


@app.command("ocr-images")
def ocr_images(limit: int = typer.Option(100, help="Max images to process")) -> None:
    from ai_offer_catcher.pipeline import PipelineRunner

    settings, repo = _build_repo()
    processed = PipelineRunner(settings, repo).ocr_images(limit)
    typer.echo(f"OCR processed {processed} images.")


@app.command("extract-questions")
def extract_questions(limit: int = typer.Option(50, help="Max posts to process")) -> None:
    from ai_offer_catcher.pipeline import PipelineRunner

    settings, repo = _build_repo()
    processed = PipelineRunner(settings, repo).extract_questions(limit)
    typer.echo(f"Extracted questions from {processed} posts.")


@app.command("merge-questions")
def merge_questions(limit: int = typer.Option(200, help="Max extracted questions to process")) -> None:
    from ai_offer_catcher.pipeline import PipelineRunner

    settings, repo = _build_repo()
    processed = PipelineRunner(settings, repo).merge_questions(limit)
    typer.echo(f"Merged {processed} extracted questions.")


@app.command("report")
def report(
    format: str = typer.Option("json", "--format", help="json or csv"),
    output: str | None = typer.Option(None, help="Optional output path"),
) -> None:
    _, repo = _build_repo()
    written = generate_report(repo, format, output)
    if written:
        typer.echo(f"Report written to {written}")


@pipeline_app.command("run")
def pipeline_run(
    job_name: str = typer.Option(..., help="Logical crawl job name"),
    keywords_file: str | None = typer.Option(None, help="Optional keywords file"),
    max_pages: int = typer.Option(200, help="Max pages per keyword"),
    date_from: str | None = typer.Option(None, help="Inclusive start date, e.g. 2025-01-20"),
    date_to: str | None = typer.Option(None, help="Inclusive end date; omit to crawl until now"),
    limit: int = typer.Option(100, help="Stage processing limit"),
) -> None:
    from ai_offer_catcher.pipeline import PipelineRunner

    settings, repo = _build_repo()
    keywords = _load_keywords(settings)
    if keywords_file:
        keywords = [line.strip() for line in Path(keywords_file).read_text(encoding="utf-8").splitlines() if line.strip()]
    PipelineRunner(settings, repo).run_pipeline(
        job_name=job_name,
        keywords=keywords,
        max_pages=max_pages,
        limit=limit,
        date_from=parse_cli_datetime(date_from),
        date_to=parse_cli_datetime(date_to),
    )
    typer.echo("Pipeline finished.")


@pipeline_app.command("daily-sync")
def pipeline_daily_sync(
    job_name: str = typer.Option("xhs_daily_sync", help="Logical crawl job name"),
    keywords_file: str | None = typer.Option(None, help="Optional keywords file"),
    date_from: str = typer.Option("2025-01-20", help="Inclusive start date"),
    date_to: str | None = typer.Option(None, help="Inclusive end date; omit to crawl until now"),
    max_pages: int = typer.Option(200, help="Max pages per keyword"),
    batch_limit: int = typer.Option(100, help="Per-stage batch size while draining"),
) -> None:
    from ai_offer_catcher.pipeline import PipelineRunner

    settings, repo = _build_repo()
    keywords = _load_keywords(settings)
    if keywords_file:
        keywords = [line.strip() for line in Path(keywords_file).read_text(encoding="utf-8").splitlines() if line.strip()]
    runner = PipelineRunner(settings, repo)
    runner.run_pipeline(
        job_name=job_name,
        keywords=keywords,
        max_pages=max_pages,
        limit=batch_limit,
        date_from=parse_cli_datetime(date_from),
        date_to=parse_cli_datetime(date_to),
    )
    typer.echo("Daily sync finished.")


if __name__ == "__main__":
    app()
