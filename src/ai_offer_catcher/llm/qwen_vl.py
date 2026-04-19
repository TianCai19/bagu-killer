from __future__ import annotations

import logging
from pathlib import Path
from typing import Iterable

import torch

logger = logging.getLogger(__name__)


class QwenVLModel:
    def __init__(self, model_path: Path, device: str) -> None:
        self.model_path = str(model_path)
        self.device = device
        self._model = None
        self._processor = None

    def _load(self) -> None:
        if self._model is not None and self._processor is not None:
            return
        from PIL import Image
        from transformers import AutoProcessor, Qwen3VLForConditionalGeneration

        self._pil_image = Image
        self._processor = AutoProcessor.from_pretrained(self.model_path, trust_remote_code=True)
        self._model = Qwen3VLForConditionalGeneration.from_pretrained(
            self.model_path,
            torch_dtype=torch.bfloat16 if self.device.startswith("cuda") else torch.float32,
            device_map=self.device if self.device.startswith("cuda") else None,
            trust_remote_code=True,
        )
        if not self.device.startswith("cuda"):
            self._model = self._model.to(self.device)

    def generate(self, prompt: str, image_paths: Iterable[str] | None = None, max_new_tokens: int = 1024) -> str:
        self._load()
        assert self._model is not None
        assert self._processor is not None
        image_paths = list(image_paths or [])

        messages: list[dict] = [{"role": "user", "content": []}]
        for image_path in image_paths:
            messages[0]["content"].append({"type": "image", "image": image_path})
        messages[0]["content"].append({"type": "text", "text": prompt})

        chat_text = self._processor.apply_chat_template(messages, tokenize=False, add_generation_prompt=True)
        images = [self._pil_image.open(path).convert("RGB") for path in image_paths]
        model_inputs = self._processor(
            text=[chat_text],
            images=images if images else None,
            padding=True,
            return_tensors="pt",
        )
        model_inputs = {key: value.to(self._model.device) if hasattr(value, "to") else value for key, value in model_inputs.items()}
        generated_ids = self._model.generate(**model_inputs, max_new_tokens=max_new_tokens)
        trimmed = [
            output_ids[len(input_ids):]
            for input_ids, output_ids in zip(model_inputs["input_ids"], generated_ids)
        ]
        decoded = self._processor.batch_decode(trimmed, skip_special_tokens=True, clean_up_tokenization_spaces=False)
        return decoded[0].strip()
