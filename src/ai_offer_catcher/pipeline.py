from __future__ import annotations

import asyncio
import logging
from datetime import datetime

from ai_offer_catcher.artifacts import ArtifactStore
from ai_offer_catcher.crawler.xhs_crawler import crawl_xiaohongshu
from ai_offer_catcher.llm.qwen_embedding import QwenEmbeddingModel
from ai_offer_catcher.llm.qwen_vl import QwenVLModel
from ai_offer_catcher.stages.classify import PostClassifier
from ai_offer_catcher.stages.extract import QuestionExtractionStage
from ai_offer_catcher.stages.merge import QuestionMergeStage
from ai_offer_catcher.stages.ocr import ImageOCRStage
from ai_offer_catcher.utils import build_prompt_renderer

logger = logging.getLogger(__name__)


class PipelineRunner:
    def __init__(self, settings, repo) -> None:
        self.settings = settings
        self.repo = repo
        self.artifacts = ArtifactStore(settings.artifact_root)
        self.prompt_env = build_prompt_renderer(settings.prompt_dir)

    def run_pipeline(
        self,
        job_name: str,
        keywords: list[str],
        max_pages: int,
        limit: int = 100,
        date_from: datetime | None = None,
        date_to: datetime | None = None,
    ) -> None:
        asyncio.run(
            crawl_xiaohongshu(
                self.settings,
                self.repo,
                self.artifacts,
                job_name,
                keywords,
                max_pages,
                date_from=date_from,
                date_to=date_to,
            )
        )
        self.drain_all_stages(limit)

    def drain_all_stages(self, batch_limit: int) -> dict[str, int]:
        stats = {
            "classified": self._drain_stage("classify", self.classify_posts, batch_limit),
            "ocr": self._drain_stage("ocr", self.ocr_images, batch_limit),
            "extracted": self._drain_stage("extract", self.extract_questions, batch_limit),
            "merged": self._drain_stage("merge", self.merge_questions, batch_limit),
        }
        logger.info("Pipeline drain finished: %s", stats)
        return stats

    def _drain_stage(self, stage_name: str, stage_fn, batch_limit: int) -> int:
        total = 0
        while True:
            processed = stage_fn(batch_limit)
            total += processed
            logger.info("Stage %s processed batch=%s total=%s", stage_name, processed, total)
            if processed < batch_limit:
                break
        return total

    def classify_posts(self, limit: int) -> int:
        model = QwenVLModel(self.settings.classify_model_path, self.settings.model_device)
        return PostClassifier(self.repo, self.prompt_env, model, self.artifacts).run(limit)

    def ocr_images(self, limit: int) -> int:
        model = QwenVLModel(self.settings.ocr_model_path, self.settings.model_device)
        return ImageOCRStage(self.repo, self.prompt_env, model, self.artifacts).run(limit)

    def extract_questions(self, limit: int) -> int:
        model = QwenVLModel(self.settings.extract_model_path, self.settings.model_device)
        return QuestionExtractionStage(self.repo, self.prompt_env, model, self.artifacts).run(limit)

    def merge_questions(self, limit: int) -> int:
        embed_model = QwenEmbeddingModel(self.settings.embed_model_path, self.settings.model_device)
        judge_model = QwenVLModel(self.settings.extract_model_path, self.settings.model_device)
        return QuestionMergeStage(
            self.repo,
            self.prompt_env,
            embed_model,
            judge_model,
            self.artifacts,
            similarity_threshold=self.settings.similarity_threshold,
            review_threshold=self.settings.similarity_review_threshold,
        ).run(limit)
