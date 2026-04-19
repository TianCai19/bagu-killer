from __future__ import annotations

import logging
import re

from ai_offer_catcher.artifacts import ArtifactStore
from ai_offer_catcher.models.schemas import ClassificationResult, PostLabel
from ai_offer_catcher.utils import extract_first_json_object, render_prompt

logger = logging.getLogger(__name__)


class PostClassifier:
    PROMPT_VERSION = "post_classification_v2"
    SUSPICIOUS_NICKNAME_PATTERNS = [
        r"大厂",
        r"面经",
        r"offer",
        r"上岸",
        r"秋招",
        r"春招",
        r"校招",
        r"求职",
        r"内推",
        r"辅导",
        r"陪跑",
        r"简历",
        r"刷题",
    ]

    def __init__(self, repo, prompt_env, model, artifacts: ArtifactStore) -> None:
        self.repo = repo
        self.prompt_env = prompt_env
        self.model = model
        self.artifacts = artifacts

    def run(self, limit: int) -> int:
        processed = 0
        for post in self.repo.list_posts_for_classification(self.PROMPT_VERSION, limit):
            nickname = (post.get("author_nickname") or "").strip()
            suspicious_hits = [pattern for pattern in self.SUSPICIOUS_NICKNAME_PATTERNS if re.search(pattern, nickname, re.I)]
            prompt = render_prompt(
                self.prompt_env,
                "post_classification.jinja2",
                author_nickname=nickname,
                title=post.get("title") or "",
                content=post.get("content") or "",
                image_context="",
                suspicious_nickname_terms=", ".join(suspicious_hits) if suspicious_hits else "无",
            )
            raw_output = self.model.generate(prompt)
            try:
                payload = extract_first_json_object(raw_output)
                result = ClassificationResult.model_validate(payload)
            except Exception as exc:
                logger.warning("Classification parse failed for post=%s: %s", post["id"], exc)
                payload = {"raw_output": raw_output}
                result = ClassificationResult()
            if suspicious_hits:
                reason = f"作者昵称含高风险营销/包装信号: {', '.join(suspicious_hits)}"
                if reason not in result.reasons:
                    result.reasons.insert(0, reason)
                result.review_needed = True
                if result.primary_label == PostLabel.UNCLEAR:
                    result.primary_label = PostLabel.AD
                    result.keep_for_extraction = False
                    result.confidence = max(result.confidence, 0.7)
            artifact_path = self.artifacts.write_json(
                f"classify/post_{post['id']}.json",
                {"prompt": prompt, "raw_output": raw_output, "parsed": payload},
            )
            self.repo.insert_classification(
                raw_post_id=post["id"],
                model_name=self.model.model_path,
                prompt_version=self.PROMPT_VERSION,
                result=result,
                output_payload=payload,
                artifact_path=artifact_path,
            )
            processed += 1
        return processed
