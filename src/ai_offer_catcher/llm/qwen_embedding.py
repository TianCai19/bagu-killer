from __future__ import annotations

from pathlib import Path
from typing import Iterable

import torch


class QwenEmbeddingModel:
    def __init__(self, model_path: Path, device: str) -> None:
        self.model_path = str(model_path)
        self.device = device
        self._tokenizer = None
        self._model = None

    def _load(self) -> None:
        if self._tokenizer is not None and self._model is not None:
            return
        from transformers import AutoModel, AutoTokenizer

        self._tokenizer = AutoTokenizer.from_pretrained(
            self.model_path,
            trust_remote_code=True,
            use_fast=False,
        )
        self._model = AutoModel.from_pretrained(
            self.model_path,
            trust_remote_code=True,
            torch_dtype=torch.bfloat16 if self.device.startswith("cuda") else torch.float32,
        )
        self._model = self._model.to(self.device)
        self._model.eval()

    @torch.inference_mode()
    def encode(self, texts: Iterable[str]) -> list[list[float]]:
        self._load()
        assert self._tokenizer is not None
        assert self._model is not None
        texts = list(texts)
        inputs = self._tokenizer(
            texts,
            padding=True,
            truncation=True,
            max_length=2048,
            return_tensors="pt",
        )
        inputs = {key: value.to(self.device) for key, value in inputs.items()}
        outputs = self._model(**inputs)
        hidden = outputs.last_hidden_state
        mask = inputs["attention_mask"].unsqueeze(-1)
        pooled = (hidden * mask).sum(dim=1) / mask.sum(dim=1).clamp(min=1)
        pooled = torch.nn.functional.normalize(pooled, p=2, dim=1)
        return pooled.float().cpu().tolist()
