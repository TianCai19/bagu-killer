from __future__ import annotations

import logging

from ai_offer_catcher.artifacts import ArtifactStore
from ai_offer_catcher.models.schemas import ExtractionResult
from ai_offer_catcher.utils import extract_first_json_object, fingerprint_text, normalize_question, render_prompt

logger = logging.getLogger(__name__)


class QuestionExtractionStage:
    PROMPT_VERSION = "question_extract_v1"

    def __init__(self, repo, prompt_env, model, artifacts: ArtifactStore) -> None:
        self.repo = repo
        self.prompt_env = prompt_env
        self.model = model
        self.artifacts = artifacts

    def run(self, limit: int) -> int:
        processed = 0
        for post in self.repo.list_posts_for_extraction(limit):
            prompt = render_prompt(
                self.prompt_env,
                "question_extraction.jinja2",
                title=post.get("title") or "",
                content=post.get("content") or "",
                ocr_text=post.get("merged_text") or "",
            )
            raw_output = self.model.generate(prompt)
            try:
                payload = extract_first_json_object(raw_output)
                result = ExtractionResult.model_validate(payload)
            except Exception as exc:
                logger.warning("Extraction parse failed for post=%s: %s", post["id"], exc)
                payload = {"raw_output": raw_output}
                result = ExtractionResult()
            artifact_path = self.artifacts.write_json(
                f"extract/post_{post['id']}.json",
                {"prompt": prompt, "raw_output": raw_output, "parsed": payload},
            )
            extraction = self.repo.insert_extraction(
                raw_post_id=post["id"],
                model_name=self.model.model_path,
                prompt_version=self.PROMPT_VERSION,
                result=result,
                output_payload=payload,
                artifact_path=artifact_path,
            )
            seen: set[str] = set()
            for question in result.questions:
                normalized = normalize_question(question.raw_text)
                if not normalized or normalized in seen:
                    continue
                seen.add(normalized)
                self.repo.insert_extracted_question(
                    raw_post_id=post["id"],
                    post_extraction_id=extraction["id"],
                    raw_text=question.raw_text,
                    normalized_text=normalized,
                    fingerprint=fingerprint_text(normalized),
                    question_type=question.question_type.value,
                    evidence_span=question.evidence_span,
                )
            processed += 1
        return processed
