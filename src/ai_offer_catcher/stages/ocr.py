from __future__ import annotations

import logging

from ai_offer_catcher.artifacts import ArtifactStore
from ai_offer_catcher.utils import render_prompt

logger = logging.getLogger(__name__)


class ImageOCRStage:
    PROMPT_VERSION = "image_ocr_v1"

    def __init__(self, repo, prompt_env, model, artifacts: ArtifactStore) -> None:
        self.repo = repo
        self.prompt_env = prompt_env
        self.model = model
        self.artifacts = artifacts

    def run(self, limit: int) -> int:
        processed = 0
        for image_row in self.repo.list_images_for_ocr(limit):
            prompt = render_prompt(self.prompt_env, "image_ocr.jinja2")
            raw_output = self.model.generate(prompt, image_paths=[image_row["local_path"]])
            artifact_path = self.artifacts.write_json(
                f"ocr/image_{image_row['id']}.json",
                {"prompt": prompt, "raw_output": raw_output, "image_path": image_row["local_path"]},
            )
            self.repo.insert_ocr_result(
                post_image_id=image_row["id"],
                model_name=self.model.model_path,
                prompt_version=self.PROMPT_VERSION,
                ocr_text=raw_output.strip(),
                confidence=1.0 if raw_output.strip() else 0.0,
                model_output_json={"raw_output": raw_output},
                artifact_path=artifact_path,
            )
            self.repo.refresh_merged_post_text(image_row["raw_post_id"])
            processed += 1
        return processed
