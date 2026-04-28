from __future__ import annotations

import asyncio
import logging
import random
from datetime import datetime

from ai_offer_catcher.app_settings import AppSettings
from ai_offer_catcher.artifacts import ArtifactStore
from ai_offer_catcher.crawler.media_crawler_adapter import XhsCrawlerSession
from ai_offer_catcher.utils import parse_iso_datetime

logger = logging.getLogger(__name__)


def _should_skip_by_date(published_at: datetime | None, date_from: datetime | None, date_to: datetime | None) -> bool:
    if published_at is None:
        return False
    if date_to and published_at > date_to:
        return True
    if date_from and published_at < date_from:
        return True
    return False


async def crawl_xiaohongshu(
    settings: AppSettings,
    repo,
    artifacts: ArtifactStore,
    job_name: str,
    keywords: list[str],
    max_pages: int,
    date_from: datetime | None = None,
    date_to: datetime | None = None,
    sort_type: str = "latest",
) -> None:
    job = repo.get_or_create_crawl_job(
        job_name=job_name,
        keywords=keywords,
        max_pages=max_pages,
        date_from=date_from,
        date_to=date_to,
        sort_type=sort_type,
    )
    crawl_job_id = job["id"]
    job_failed = False

    async with XhsCrawlerSession(settings) as session:
        from media_platform.xhs.help import get_search_id

        for keyword in keywords:
            previous_checkpoint = repo.get_keyword_checkpoint(
                keyword=keyword,
                date_from=date_from,
                date_to=date_to,
                sort_type=sort_type,
            )
            watermark = previous_checkpoint["newest_published_at"] if previous_checkpoint else None
            if watermark is None:
                watermark = repo.get_keyword_watermark_from_hits(keyword, date_from=date_from, date_to=date_to)
            search_id = get_search_id()
            stale_pages = 0
            stop_reason = None

            repo.upsert_keyword_checkpoint(
                keyword,
                date_from=date_from,
                date_to=date_to,
                sort_type=sort_type,
                status="running",
                last_crawl_job_id=crawl_job_id,
                stop_reason=None,
            )

            for page_no in range(1, max_pages + 1):
                repo.upsert_crawl_page(crawl_job_id, keyword, page_no, status="running", search_id=search_id)
                try:
                    response = await session.search_page(keyword, page_no, search_id, sort_type=sort_type)
                    response_artifact = artifacts.write_json(
                        f"crawl/{crawl_job_id}/{keyword}/page_{page_no}_search.json",
                        response,
                    )
                    repo.upsert_crawl_page(
                        crawl_job_id,
                        keyword,
                        page_no,
                        status="completed",
                        search_id=search_id,
                        raw_response_artifact_path=response_artifact,
                    )
                    repo.log_event(crawl_job_id, "crawl", "search_page", f"{keyword}:{page_no}", "completed", {"artifact_path": response_artifact})

                    items = response.get("items", [])
                    if not items:
                        stop_reason = "empty_page"
                        break

                    page_seen = 0
                    page_new_posts = 0
                    page_old_posts = 0
                    oldest_in_page: datetime | None = None
                    newest_in_page: datetime | None = None

                    for item in items:
                        if item.get("model_type") in {"rec_query", "hot_query"}:
                            continue
                        note_detail = await session.fetch_note_detail(
                            note_id=item.get("id"),
                            xsec_source=item.get("xsec_source"),
                            xsec_token=item.get("xsec_token"),
                        )
                        if not note_detail:
                            continue

                        record = session.note_to_record(note_detail)
                        published_dt = parse_iso_datetime(record.published_at)
                        if published_dt:
                            oldest_in_page = published_dt if oldest_in_page is None else min(oldest_in_page, published_dt)
                            newest_in_page = published_dt if newest_in_page is None else max(newest_in_page, published_dt)

                        if _should_skip_by_date(published_dt, date_from, date_to):
                            if date_from and published_dt and published_dt < date_from:
                                page_old_posts += 1
                            continue

                        existing_post = repo.get_raw_post_by_source_note_id(record.source_note_id)
                        if existing_post:
                            page_old_posts += 1

                        note_artifact = artifacts.write_json(
                            f"crawl/{crawl_job_id}/notes/{record.source_note_id}.json",
                            note_detail,
                        )
                        raw_post = repo.upsert_raw_post(record, note_artifact)
                        repo.link_keyword_hit(raw_post["id"], keyword, crawl_job_id, page_no)

                        if not existing_post:
                            page_new_posts += 1

                        for image in record.images:
                            content = await session.download_media(image.image_url)
                            if content is None:
                                continue
                            local_path = artifacts.write_binary(
                                f"crawl/{crawl_job_id}/images/{record.source_note_id}_{image.image_index}.jpg",
                                content,
                            )
                            downloaded = session.attach_downloaded_image(image, content, local_path)
                            repo.upsert_post_image(raw_post["id"], downloaded)

                        page_seen += 1
                        
                        # Dynamic sleep based on content length and image count to simulate reading
                        base_sleep = settings.request_sleep_seconds
                        jitter = random.uniform(-0.5, 1.5)
                        content_len = len(record.content) if record.content else 0
                        image_cnt = len(record.images) if record.images else 0
                        
                        # Add extra sleep for longer posts (e.g. 0.5s per 100 chars, up to 3s)
                        read_sleep = min(content_len * 0.005, 3.0)
                        # Add extra sleep for scanning images (e.g. 0.2s per image, up to 2s)
                        img_sleep = min(image_cnt * 0.2, 2.0)
                        
                        dynamic_sleep = max(1.0, base_sleep + jitter + read_sleep + img_sleep)
                        logger.info("Fetched note %s, simulating read for %.2f seconds (len: %d, img: %d)", record.source_note_id, dynamic_sleep, content_len, image_cnt)
                        await asyncio.sleep(dynamic_sleep)

                    if watermark and oldest_in_page and oldest_in_page <= watermark and page_new_posts == 0:
                        stale_pages += 1
                    else:
                        stale_pages = 0

                    repo.upsert_keyword_checkpoint(
                        keyword,
                        date_from=date_from,
                        date_to=date_to,
                        sort_type=sort_type,
                        status="running",
                        last_crawl_job_id=crawl_job_id,
                        last_completed_page=page_no,
                        newest_published_at=newest_in_page,
                        oldest_published_at=oldest_in_page,
                        total_pages_crawled=1,
                        total_posts_seen=page_seen,
                        total_new_posts=page_new_posts,
                        consecutive_stale_pages=stale_pages,
                        stop_reason=None,
                    )

                    # Newest-first crawl can stop when this page is already fully below the watermark.
                    if watermark and oldest_in_page and oldest_in_page <= watermark and page_new_posts == 0:
                        stop_reason = "reached_existing_watermark"
                        break

                    # Historical backfill can stop once we have crossed below the requested lower bound.
                    if date_from and oldest_in_page and oldest_in_page < date_from and page_new_posts == 0:
                        stop_reason = "reached_date_from_boundary"
                        break
                except Exception as exc:
                    job_failed = True
                    logger.exception("Failed to crawl keyword=%s page=%s", keyword, page_no)
                    repo.upsert_crawl_page(
                        crawl_job_id,
                        keyword,
                        page_no,
                        status="failed",
                        search_id=search_id,
                        error_message=str(exc),
                    )
                    repo.upsert_keyword_checkpoint(
                        keyword,
                        date_from=date_from,
                        date_to=date_to,
                        sort_type=sort_type,
                        status="failed",
                        last_crawl_job_id=crawl_job_id,
                        stop_reason=str(exc),
                    )
                    repo.log_event(crawl_job_id, "crawl", "search_page", f"{keyword}:{page_no}", "failed", {"error": str(exc)})
                    break

            repo.upsert_keyword_checkpoint(
                keyword,
                date_from=date_from,
                date_to=date_to,
                sort_type=sort_type,
                status="completed" if stop_reason != "failed" else "failed",
                last_crawl_job_id=crawl_job_id,
                stop_reason=stop_reason or "max_pages_reached",
            )

    repo.finish_crawl_job(crawl_job_id, "failed" if job_failed else "completed")
