from __future__ import annotations

import json
import logging
from datetime import datetime
from typing import Any

from ai_offer_catcher.models.schemas import ClassificationResult, CrawlPostImage, CrawlPostRecord, ExtractionResult
from ai_offer_catcher.utils import build_window_key

logger = logging.getLogger(__name__)


class Repository:
    def __init__(self, db) -> None:
        self.db = db

    def get_or_create_crawl_job(
        self,
        job_name: str,
        keywords: list[str],
        max_pages: int,
        date_from: datetime | None = None,
        date_to: datetime | None = None,
        sort_type: str = "latest",
    ) -> dict[str, Any]:
        with self.db.connect() as conn, conn.cursor() as cur:
            cur.execute(
                """
                SELECT * FROM crawl_jobs
                WHERE job_name = %s AND platform = 'xhs'
                  AND COALESCE(date_from, '-infinity'::timestamptz) = COALESCE(%s::timestamptz, '-infinity'::timestamptz)
                  AND COALESCE(date_to, 'infinity'::timestamptz) = COALESCE(%s::timestamptz, 'infinity'::timestamptz)
                  AND sort_type = %s
                ORDER BY id DESC
                LIMIT 1
                """,
                (job_name, date_from, date_to, sort_type),
            )
            row = cur.fetchone()
            if row:
                return row
            cur.execute(
                """
                INSERT INTO crawl_jobs (job_name, keywords_json, max_pages, date_from, date_to, sort_type, status, started_at)
                VALUES (%s, %s::jsonb, %s, %s, %s, %s, 'running', NOW())
                RETURNING *
                """,
                (job_name, json.dumps(keywords, ensure_ascii=False), max_pages, date_from, date_to, sort_type),
            )
            conn.commit()
            return cur.fetchone()

    def get_keyword_checkpoint(
        self,
        keyword: str,
        date_from: datetime | None = None,
        date_to: datetime | None = None,
        sort_type: str = "latest",
    ) -> dict[str, Any] | None:
        return self.fetch_one(
            """
            SELECT *
            FROM crawl_keyword_checkpoints
            WHERE platform = 'xhs' AND keyword = %s AND window_key = %s AND sort_type = %s
            ORDER BY id DESC
            LIMIT 1
            """,
            (keyword, build_window_key(date_from, date_to), sort_type),
        )

    def get_keyword_watermark_from_hits(
        self,
        keyword: str,
        date_from: datetime | None = None,
        date_to: datetime | None = None,
    ) -> datetime | None:
        row = self.fetch_one(
            """
            SELECT MAX(rp.published_at) AS newest_published_at
            FROM raw_posts rp
            JOIN post_keyword_hits pkh ON pkh.raw_post_id = rp.id
            WHERE rp.platform = 'xhs'
              AND pkh.keyword = %s
              AND (%s::timestamptz IS NULL OR rp.published_at >= %s::timestamptz)
              AND (%s::timestamptz IS NULL OR rp.published_at <= %s::timestamptz)
            """,
            (keyword, date_from, date_from, date_to, date_to),
        )
        return row["newest_published_at"] if row else None

    def upsert_keyword_checkpoint(
        self,
        keyword: str,
        *,
        date_from: datetime | None = None,
        date_to: datetime | None = None,
        sort_type: str = "latest",
        status: str,
        last_crawl_job_id: int | None = None,
        last_completed_page: int | None = None,
        newest_published_at: datetime | None = None,
        oldest_published_at: datetime | None = None,
        total_pages_crawled: int = 0,
        total_posts_seen: int = 0,
        total_new_posts: int = 0,
        consecutive_stale_pages: int = 0,
        stop_reason: str | None = None,
    ) -> dict[str, Any]:
        return self.fetch_one(
            """
            INSERT INTO crawl_keyword_checkpoints (
                platform, keyword, window_key, date_from, date_to, sort_type, status, last_crawl_job_id,
                last_completed_page, newest_published_at, oldest_published_at, total_pages_crawled,
                total_posts_seen, total_new_posts, consecutive_stale_pages, stop_reason
            )
            VALUES ('xhs', %s, %s, %s, %s, %s, %s, %s, COALESCE(%s, 0), %s, %s, %s, %s, %s, %s, %s)
            ON CONFLICT (platform, keyword, window_key, sort_type)
            DO UPDATE SET
                status = EXCLUDED.status,
                last_crawl_job_id = COALESCE(EXCLUDED.last_crawl_job_id, crawl_keyword_checkpoints.last_crawl_job_id),
                last_completed_page = COALESCE(EXCLUDED.last_completed_page, crawl_keyword_checkpoints.last_completed_page),
                newest_published_at = CASE
                    WHEN crawl_keyword_checkpoints.newest_published_at IS NULL THEN EXCLUDED.newest_published_at
                    WHEN EXCLUDED.newest_published_at IS NULL THEN crawl_keyword_checkpoints.newest_published_at
                    ELSE GREATEST(crawl_keyword_checkpoints.newest_published_at, EXCLUDED.newest_published_at)
                END,
                oldest_published_at = CASE
                    WHEN crawl_keyword_checkpoints.oldest_published_at IS NULL THEN EXCLUDED.oldest_published_at
                    WHEN EXCLUDED.oldest_published_at IS NULL THEN crawl_keyword_checkpoints.oldest_published_at
                    ELSE LEAST(crawl_keyword_checkpoints.oldest_published_at, EXCLUDED.oldest_published_at)
                END,
                total_pages_crawled = crawl_keyword_checkpoints.total_pages_crawled + EXCLUDED.total_pages_crawled,
                total_posts_seen = crawl_keyword_checkpoints.total_posts_seen + EXCLUDED.total_posts_seen,
                total_new_posts = crawl_keyword_checkpoints.total_new_posts + EXCLUDED.total_new_posts,
                consecutive_stale_pages = EXCLUDED.consecutive_stale_pages,
                stop_reason = EXCLUDED.stop_reason,
                updated_at = NOW()
            RETURNING *
            """,
            (
                keyword,
                build_window_key(date_from, date_to),
                date_from,
                date_to,
                sort_type,
                status,
                last_crawl_job_id,
                last_completed_page,
                newest_published_at,
                oldest_published_at,
                total_pages_crawled,
                total_posts_seen,
                total_new_posts,
                consecutive_stale_pages,
                stop_reason,
            ),
        )

    def finish_crawl_job(self, crawl_job_id: int, status: str) -> None:
        self.execute(
            """
            UPDATE crawl_jobs
            SET status = %s, finished_at = NOW(), updated_at = NOW()
            WHERE id = %s
            """,
            (status, crawl_job_id),
        )

    def get_crawl_page(self, crawl_job_id: int, keyword: str, page_no: int) -> dict[str, Any] | None:
        return self.fetch_one(
            """
            SELECT * FROM crawl_job_pages
            WHERE crawl_job_id = %s AND keyword = %s AND page_no = %s
            """,
            (crawl_job_id, keyword, page_no),
        )

    def upsert_crawl_page(
        self,
        crawl_job_id: int,
        keyword: str,
        page_no: int,
        status: str,
        search_id: str | None = None,
        raw_response_artifact_path: str | None = None,
        error_message: str | None = None,
    ) -> dict[str, Any]:
        return self.fetch_one(
            """
            INSERT INTO crawl_job_pages (crawl_job_id, keyword, page_no, status, search_id, raw_response_artifact_path, error_message)
            VALUES (%s, %s, %s, %s, %s, %s, %s)
            ON CONFLICT (crawl_job_id, keyword, page_no)
            DO UPDATE SET
                status = EXCLUDED.status,
                search_id = COALESCE(EXCLUDED.search_id, crawl_job_pages.search_id),
                raw_response_artifact_path = COALESCE(EXCLUDED.raw_response_artifact_path, crawl_job_pages.raw_response_artifact_path),
                error_message = EXCLUDED.error_message,
                updated_at = NOW()
            RETURNING *
            """,
            (crawl_job_id, keyword, page_no, status, search_id, raw_response_artifact_path, error_message),
        )

    def log_event(
        self,
        crawl_job_id: int | None,
        stage_name: str,
        entity_type: str,
        entity_id: str | None,
        status: str,
        payload: dict[str, Any],
    ) -> None:
        self.execute(
            """
            INSERT INTO crawl_events (crawl_job_id, stage_name, entity_type, entity_id, status, payload)
            VALUES (%s, %s, %s, %s, %s, %s::jsonb)
            """,
            (crawl_job_id, stage_name, entity_type, entity_id, status, json.dumps(payload, ensure_ascii=False)),
        )

    def upsert_raw_post(self, post: CrawlPostRecord, raw_note_artifact_path: str | None) -> dict[str, Any]:
        return self.fetch_one(
            """
            INSERT INTO raw_posts (
                platform, source_note_id, note_url, xsec_token, xsec_source, note_type, title, content,
                author_id, author_nickname, author_avatar, ip_location, like_count, collect_count,
                comment_count, share_count, published_at, raw_note_json, raw_note_artifact_path, merged_text, updated_at
            )
            VALUES (
                'xhs', %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s::jsonb, %s, %s, NOW()
            )
            ON CONFLICT (platform, source_note_id)
            DO UPDATE SET
                note_url = EXCLUDED.note_url,
                xsec_token = EXCLUDED.xsec_token,
                xsec_source = EXCLUDED.xsec_source,
                note_type = EXCLUDED.note_type,
                title = EXCLUDED.title,
                content = EXCLUDED.content,
                author_id = EXCLUDED.author_id,
                author_nickname = EXCLUDED.author_nickname,
                author_avatar = EXCLUDED.author_avatar,
                ip_location = EXCLUDED.ip_location,
                like_count = EXCLUDED.like_count,
                collect_count = EXCLUDED.collect_count,
                comment_count = EXCLUDED.comment_count,
                share_count = EXCLUDED.share_count,
                published_at = EXCLUDED.published_at,
                raw_note_json = EXCLUDED.raw_note_json,
                raw_note_artifact_path = EXCLUDED.raw_note_artifact_path,
                merged_text = EXCLUDED.merged_text,
                updated_at = NOW()
            RETURNING *
            """,
            (
                post.source_note_id,
                post.note_url,
                post.xsec_token,
                post.xsec_source,
                post.note_type,
                post.title,
                post.content,
                post.author_id,
                post.author_nickname,
                post.author_avatar,
                post.ip_location,
                post.like_count,
                post.collect_count,
                post.comment_count,
                post.share_count,
                post.published_at,
                json.dumps(post.raw_note_json, ensure_ascii=False),
                raw_note_artifact_path,
                post.merged_text,
            ),
        )

    def get_raw_post_by_source_note_id(self, source_note_id: str) -> dict[str, Any] | None:
        return self.fetch_one(
            """
            SELECT *
            FROM raw_posts
            WHERE platform = 'xhs' AND source_note_id = %s
            LIMIT 1
            """,
            (source_note_id,),
        )

    def link_keyword_hit(self, raw_post_id: int, keyword: str, crawl_job_id: int, hit_page_no: int) -> None:
        self.execute(
            """
            INSERT INTO post_keyword_hits (raw_post_id, keyword, crawl_job_id, hit_page_no)
            VALUES (%s, %s, %s, %s)
            ON CONFLICT (raw_post_id, keyword, crawl_job_id, hit_page_no) DO NOTHING
            """,
            (raw_post_id, keyword, crawl_job_id, hit_page_no),
        )

    def upsert_post_image(self, raw_post_id: int, image: CrawlPostImage) -> dict[str, Any]:
        return self.fetch_one(
            """
            INSERT INTO post_images (raw_post_id, image_index, image_url, local_path, sha256, status, updated_at)
            VALUES (%s, %s, %s, %s, %s, 'downloaded', NOW())
            ON CONFLICT (raw_post_id, image_index)
            DO UPDATE SET
                image_url = EXCLUDED.image_url,
                local_path = EXCLUDED.local_path,
                sha256 = EXCLUDED.sha256,
                status = EXCLUDED.status,
                updated_at = NOW()
            RETURNING *
            """,
            (raw_post_id, image.image_index, image.image_url, image.local_path, image.sha256),
        )

    def list_posts_for_classification(self, prompt_version: str, limit: int) -> list[dict[str, Any]]:
        return self.fetch_all(
            """
            SELECT rp.*
            FROM raw_posts rp
            WHERE NOT EXISTS (
                SELECT 1
                FROM post_classifications pc
                WHERE pc.raw_post_id = rp.id
                  AND pc.prompt_version = %s
            )
            ORDER BY rp.id
            LIMIT %s
            """,
            (prompt_version, limit),
        )

    def insert_classification(
        self,
        raw_post_id: int,
        model_name: str,
        prompt_version: str,
        result: ClassificationResult,
        output_payload: dict[str, Any],
        artifact_path: str | None,
    ) -> None:
        self.execute(
            """
            INSERT INTO post_classifications (
                raw_post_id, model_name, prompt_version, primary_label, keep_for_extraction,
                confidence, reasons, review_needed, company_name, role_name, model_output_json, artifact_path
            )
            VALUES (%s, %s, %s, %s, %s, %s, %s::jsonb, %s, %s, %s, %s::jsonb, %s)
            """,
            (
                raw_post_id,
                model_name,
                prompt_version,
                result.primary_label.value,
                result.keep_for_extraction,
                result.confidence,
                json.dumps(result.reasons, ensure_ascii=False),
                result.review_needed,
                result.company_name,
                result.role_name,
                json.dumps(output_payload, ensure_ascii=False),
                artifact_path,
            ),
        )
        review_status = "pending" if result.review_needed else ("kept" if result.keep_for_extraction else "rejected")
        self.execute(
            "UPDATE raw_posts SET review_status = %s, updated_at = NOW() WHERE id = %s",
            (review_status, raw_post_id),
        )

    def list_images_for_ocr(self, limit: int) -> list[dict[str, Any]]:
        return self.fetch_all(
            """
            SELECT pi.*, rp.title, rp.content
            FROM post_images pi
            JOIN raw_posts rp ON rp.id = pi.raw_post_id
            WHERE pi.status = 'downloaded'
              AND rp.review_status IN ('kept', 'pending')
              AND NOT EXISTS (
                SELECT 1 FROM post_ocr_results por WHERE por.post_image_id = pi.id
              )
            ORDER BY pi.id
            LIMIT %s
            """,
            (limit,),
        )

    def insert_ocr_result(
        self,
        post_image_id: int,
        model_name: str,
        prompt_version: str,
        ocr_text: str,
        confidence: float,
        model_output_json: dict[str, Any],
        artifact_path: str | None,
    ) -> None:
        self.execute(
            """
            INSERT INTO post_ocr_results (
                post_image_id, model_name, prompt_version, ocr_text, confidence, model_output_json, artifact_path
            )
            VALUES (%s, %s, %s, %s, %s, %s::jsonb, %s)
            """,
            (post_image_id, model_name, prompt_version, ocr_text, confidence, json.dumps(model_output_json, ensure_ascii=False), artifact_path),
        )
        self.execute("UPDATE post_images SET status = 'ocr_done', updated_at = NOW() WHERE id = %s", (post_image_id,))

    def refresh_merged_post_text(self, raw_post_id: int) -> None:
        self.execute(
            """
            UPDATE raw_posts rp
            SET merged_text = concat_ws(E'\n\n',
                NULLIF(rp.title, ''),
                NULLIF(rp.content, ''),
                (
                    SELECT string_agg(NULLIF(por.ocr_text, ''), E'\n\n' ORDER BY pi.image_index)
                    FROM post_images pi
                    LEFT JOIN post_ocr_results por ON por.post_image_id = pi.id
                    WHERE pi.raw_post_id = rp.id
                )
            ),
            updated_at = NOW()
            WHERE rp.id = %s
            """,
            (raw_post_id,),
        )

    def list_posts_for_extraction(self, limit: int) -> list[dict[str, Any]]:
        return self.fetch_all(
            """
            SELECT rp.*, pc.primary_label, pc.keep_for_extraction
            FROM raw_posts rp
            JOIN LATERAL (
                SELECT *
                FROM post_classifications pc
                WHERE pc.raw_post_id = rp.id
                ORDER BY pc.id DESC
                LIMIT 1
            ) pc ON TRUE
            WHERE pc.keep_for_extraction = TRUE
              AND NOT EXISTS (
                SELECT 1 FROM post_extractions pe WHERE pe.raw_post_id = rp.id
              )
            ORDER BY rp.id
            LIMIT %s
            """,
            (limit,),
        )

    def insert_extraction(
        self,
        raw_post_id: int,
        model_name: str,
        prompt_version: str,
        result: ExtractionResult,
        output_payload: dict[str, Any],
        artifact_path: str | None,
    ) -> dict[str, Any]:
        return self.fetch_one(
            """
            INSERT INTO post_extractions (
                raw_post_id, model_name, prompt_version, company_name, role_name,
                interview_stage, is_real_experience_confidence, model_output_json, artifact_path
            )
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s::jsonb, %s)
            RETURNING *
            """,
            (
                raw_post_id,
                model_name,
                prompt_version,
                result.company_name,
                result.role_name,
                result.interview_stage,
                result.is_real_experience_confidence,
                json.dumps(output_payload, ensure_ascii=False),
                artifact_path,
            ),
        )

    def insert_extracted_question(
        self,
        raw_post_id: int,
        post_extraction_id: int,
        raw_text: str,
        normalized_text: str,
        fingerprint: str,
        question_type: str,
        evidence_span: str | None,
    ) -> None:
        self.execute(
            """
            INSERT INTO extracted_questions (
                raw_post_id, post_extraction_id, raw_text, normalized_text, fingerprint, question_type, evidence_span
            )
            VALUES (%s, %s, %s, %s, %s, %s, %s)
            """,
            (raw_post_id, post_extraction_id, raw_text, normalized_text, fingerprint, question_type, evidence_span),
        )

    def list_questions_for_merge(self, limit: int) -> list[dict[str, Any]]:
        return self.fetch_all(
            """
            SELECT eq.*, pe.company_name, pe.role_name, pe.interview_stage
            FROM extracted_questions eq
            LEFT JOIN post_extractions pe ON pe.id = eq.post_extraction_id
            WHERE eq.status = 'pending_merge'
            ORDER BY eq.id
            LIMIT %s
            """,
            (limit,),
        )

    def find_canonical_by_fingerprint(self, fingerprint: str, question_type: str) -> dict[str, Any] | None:
        return self.fetch_one(
            """
            SELECT *
            FROM canonical_questions
            WHERE fingerprint = %s AND question_type = %s
            ORDER BY id
            LIMIT 1
            """,
            (fingerprint, question_type),
        )

    def search_similar_canonicals(self, embedding: list[float], question_type: str, limit: int = 5) -> list[dict[str, Any]]:
        vector_literal = "[" + ",".join(f"{value:.8f}" for value in embedding) + "]"
        return self.fetch_all(
            """
            SELECT *,
                   1 - (embedding <=> %s::vector) AS similarity
            FROM canonical_questions
            WHERE question_type = %s AND embedding IS NOT NULL
            ORDER BY embedding <=> %s::vector
            LIMIT %s
            """,
            (vector_literal, question_type, vector_literal, limit),
        )

    def insert_canonical_question(
        self,
        canonical_text: str,
        normalized_text: str,
        fingerprint: str,
        question_type: str,
        embedding: list[float],
        first_seen_post_id: int,
    ) -> dict[str, Any]:
        vector_literal = "[" + ",".join(f"{value:.8f}" for value in embedding) + "]"
        return self.fetch_one(
            """
            INSERT INTO canonical_questions (
                canonical_text, normalized_text, fingerprint, question_type, embedding,
                first_seen_post_id, last_seen_post_id
            )
            VALUES (%s, %s, %s, %s, %s::vector, %s, %s)
            RETURNING *
            """,
            (canonical_text, normalized_text, fingerprint, question_type, vector_literal, first_seen_post_id, first_seen_post_id),
        )

    def link_question(
        self,
        raw_post_id: int,
        extracted_question_id: int,
        canonical_question_id: int,
        alias_text: str,
        normalized_text: str,
        fingerprint: str,
        merge_method: str,
        merge_score: float | None,
        review_needed: bool,
        company_name: str | None,
        role_name: str | None,
        interview_stage: str | None,
    ) -> None:
        self.execute(
            """
            INSERT INTO question_aliases (
                canonical_question_id, extracted_question_id, alias_text, normalized_text,
                fingerprint, merge_method, merge_score, review_needed
            )
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
            ON CONFLICT (canonical_question_id, extracted_question_id) DO NOTHING
            """,
            (canonical_question_id, extracted_question_id, alias_text, normalized_text, fingerprint, merge_method, merge_score, review_needed),
        )
        self.execute(
            """
            INSERT INTO post_question_links (
                raw_post_id, canonical_question_id, extracted_question_id, company_name, role_name, interview_stage
            )
            VALUES (%s, %s, %s, %s, %s, %s)
            ON CONFLICT (raw_post_id, canonical_question_id, extracted_question_id) DO NOTHING
            """,
            (raw_post_id, canonical_question_id, extracted_question_id, company_name, role_name, interview_stage),
        )
        self.execute(
            """
            UPDATE extracted_questions
            SET status = 'merged'
            WHERE id = %s
            """,
            (extracted_question_id,),
        )
        self.execute(
            """
            UPDATE canonical_questions cq
            SET post_count = sub.count_posts,
                last_seen_post_id = %s,
                updated_at = NOW()
            FROM (
                SELECT canonical_question_id, COUNT(DISTINCT raw_post_id) AS count_posts
                FROM post_question_links
                WHERE canonical_question_id = %s
                GROUP BY canonical_question_id
            ) sub
            WHERE cq.id = sub.canonical_question_id
            """,
            (raw_post_id, canonical_question_id),
        )

    def list_report_rows(self) -> list[dict[str, Any]]:
        return self.fetch_all(
            """
            SELECT
                cq.id,
                cq.canonical_text,
                cq.question_type,
                cqs.unique_post_count,
                cqs.companies,
                cqs.roles
            FROM canonical_questions cq
            LEFT JOIN canonical_question_stats cqs ON cqs.id = cq.id
            ORDER BY cqs.unique_post_count DESC NULLS LAST, cq.id
            """
        )

    def fetch_one(self, sql: str, params: tuple[Any, ...] | None = None) -> dict[str, Any] | None:
        with self.db.connect() as conn, conn.cursor() as cur:
            cur.execute(sql, params)
            row = cur.fetchone()
            conn.commit()
            return row

    def fetch_all(self, sql: str, params: tuple[Any, ...] | None = None) -> list[dict[str, Any]]:
        with self.db.connect() as conn, conn.cursor() as cur:
            cur.execute(sql, params)
            rows = list(cur.fetchall())
            conn.commit()
            return rows

    def execute(self, sql: str, params: tuple[Any, ...] | None = None) -> None:
        with self.db.connect() as conn, conn.cursor() as cur:
            cur.execute(sql, params)
            conn.commit()
