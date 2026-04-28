from __future__ import annotations

import logging
from pathlib import Path
import base64
from typing import Iterable
from openai import OpenAI

logger = logging.getLogger(__name__)

class QwenVLModel:
    def __init__(self, model_path: Path, device: str) -> None:
        # LM Studio default API URL
        # Determine model name from path for LM Studio
        self.model_path = str(model_path)
        self.api_base = "http://localhost:1234/v1"
        
        path_parts = self.model_path.split("/")
        # For paths like .../google/gemma-4-e4b, we want google/gemma-4-e4b
        if len(path_parts) >= 2 and path_parts[-2] != "huggingface_models":
            self.model_name = f"{path_parts[-2]}/{path_parts[-1]}"
        else:
            self.model_name = path_parts[-1]
        self.client = OpenAI(base_url=self.api_base, api_key="lm-studio")
        self._model = True  # Mock initialization state
        self._processor = True

    def _load(self) -> None:
        pass  # Handled by LM Studio

    def _encode_image(self, image_path: str) -> str:
        with open(image_path, "rb") as image_file:
            return base64.b64encode(image_file.read()).decode('utf-8')

    def generate(self, prompt: str, image_paths: Iterable[str] | None = None, max_new_tokens: int = 12000) -> str:
        image_paths = list(image_paths or [])
        content = []

        # Add image blocks
        for image_path in image_paths:
            base64_image = self._encode_image(image_path)
            content.append({
                "type": "image_url",
                "image_url": {
                    "url": f"data:image/jpeg;base64,{base64_image}"
                }
            })

        # Add text prompt block
        content.append({
            "type": "text",
            "text": prompt
        })

        try:
            response = self.client.chat.completions.create(
                model=self.model_name,
                messages=[
                    {"role": "user", "content": content}
                ],
                max_tokens=max_new_tokens,
                temperature=0.0,
                extra_body={"enable_thinking": False}
            )
            # Some local reasoning models might return content inside a different field or return it as empty if purely reasoning
            msg = response.choices[0].message
            return_text = msg.content or ""
            if not return_text and hasattr(msg, "reasoning_content"):
                return_text = msg.reasoning_content
            return return_text.strip()
        except Exception as e:
            logger.error(f"LM Studio API generation error: {e}")
            raise
