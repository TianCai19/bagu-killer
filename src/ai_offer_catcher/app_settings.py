from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

from dotenv import load_dotenv


@dataclass(frozen=True)
class AppSettings:
    db_dsn: str
    artifact_root: Path
    mediacrawler_root: Path
    xhs_index_url: str
    enable_cdp: bool
    cdp_headless: bool
    cdp_connect_existing: bool
    cdp_port: int
    headless: bool
    save_login_state: bool
    user_data_dir: str
    max_concurrency: int
    request_sleep_seconds: float
    enable_comments: bool
    max_comments_per_post: int
    classify_model_path: Path
    ocr_model_path: Path
    extract_model_path: Path
    embed_model_path: Path
    model_device: str
    similarity_threshold: float
    similarity_review_threshold: float
    embed_batch_size: int
    prompt_dir: Path
    keywords_file: Path

    @classmethod
    def load(cls, env_file: str | None = None) -> "AppSettings":
        load_dotenv(env_file)
        root = Path(__file__).resolve().parents[2]
        return cls(
            db_dsn=os.getenv("AI_OFFER_DB_DSN", "postgresql://postgres:123456@localhost:5432/ai_offer_catcher"),
            artifact_root=Path(os.getenv("AI_OFFER_ARTIFACT_ROOT", str(root / "artifacts"))),
            mediacrawler_root=Path(os.getenv("AI_OFFER_MEDIACRAWLER_ROOT", str(root / "MediaCrawler"))),
            xhs_index_url=os.getenv("AI_OFFER_XHS_INDEX_URL", "https://www.xiaohongshu.com"),
            enable_cdp=_get_bool("AI_OFFER_ENABLE_CDP", True),
            cdp_headless=_get_bool("AI_OFFER_CDP_HEADLESS", False),
            cdp_connect_existing=_get_bool("AI_OFFER_CDP_CONNECT_EXISTING", True),
            cdp_port=int(os.getenv("AI_OFFER_CDP_PORT", "9222")),
            headless=_get_bool("AI_OFFER_HEADLESS", False),
            save_login_state=_get_bool("AI_OFFER_SAVE_LOGIN_STATE", True),
            user_data_dir=os.getenv("AI_OFFER_USER_DATA_DIR", "xhs_user_data_dir"),
            max_concurrency=int(os.getenv("AI_OFFER_MAX_CONCURRENCY", "1")),
            request_sleep_seconds=float(os.getenv("AI_OFFER_REQUEST_SLEEP_SECONDS", "2")),
            enable_comments=_get_bool("AI_OFFER_ENABLE_COMMENTS", False),
            max_comments_per_post=int(os.getenv("AI_OFFER_MAX_COMMENTS_PER_POST", "20")),
            classify_model_path=Path(os.getenv("AI_OFFER_CLASSIFY_MODEL_PATH", "/data3/public_checkpoints/huggingface_models/Qwen3-VL-4B-Instruct")),
            ocr_model_path=Path(os.getenv("AI_OFFER_OCR_MODEL_PATH", "/data3/public_checkpoints/huggingface_models/Qwen3-VL-4B-Instruct")),
            extract_model_path=Path(os.getenv("AI_OFFER_EXTRACT_MODEL_PATH", "/data3/public_checkpoints/huggingface_models/Qwen3-VL-8B-Instruct")),
            embed_model_path=Path(os.getenv("AI_OFFER_EMBED_MODEL_PATH", "/data3/public_checkpoints/huggingface_models/Qwen3-Embedding-4B")),
            model_device=os.getenv("AI_OFFER_MODEL_DEVICE", "cuda:0"),
            similarity_threshold=float(os.getenv("AI_OFFER_SIMILARITY_THRESHOLD", "0.86")),
            similarity_review_threshold=float(os.getenv("AI_OFFER_SIMILARITY_REVIEW_THRESHOLD", "0.80")),
            embed_batch_size=int(os.getenv("AI_OFFER_EMBED_BATCH_SIZE", "8")),
            prompt_dir=Path(os.getenv("AI_OFFER_PROMPT_DIR", str(root / "config" / "prompts"))),
            keywords_file=Path(os.getenv("AI_OFFER_KEYWORDS_FILE", str(root / "config" / "keywords.txt"))),
        )


def _get_bool(name: str, default: bool) -> bool:
    raw = os.getenv(name)
    if raw is None:
        return default
    return raw.lower() in {"1", "true", "yes", "on"}
