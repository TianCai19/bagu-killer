from __future__ import annotations

from pathlib import Path
from typing import Iterable
from openai import OpenAI

class QwenEmbeddingModel:
    def __init__(self, model_path: Path, device: str) -> None:
        self.model_path = str(model_path)
        self.api_base = "http://localhost:1234/v1"
        self.model_name = str(model_path).split("/")[-1]
        self.client = OpenAI(base_url=self.api_base, api_key="lm-studio")
        self._tokenizer = True
        self._model = True

    def _load(self) -> None:
        pass  # Handled by LM Studio

    def encode(self, texts: Iterable[str]) -> list[list[float]]:
        texts = list(texts)
        if not texts:
            return []
            
        response = self.client.embeddings.create(
            model=self.model_name,
            input=texts
        )
        # Sort embeddings by their original index to preserve order
        sorted_data = sorted(response.data, key=lambda x: x.index)
        return [item.embedding for item in sorted_data]
