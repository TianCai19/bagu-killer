from __future__ import annotations

from enum import Enum
from typing import Any

from pydantic import BaseModel, Field


class PostLabel(str, Enum):
    REAL_EXPERIENCE = "real_experience"
    AD = "ad"
    COURSE_SELLING = "course_selling"
    IRRELEVANT = "irrelevant"
    QUESTION_COLLECTION = "question_collection"
    UNCLEAR = "unclear"


class QuestionType(str, Enum):
    KNOWLEDGE_QA = "knowledge_qa"
    LEETCODE_ALGO = "leetcode_algo"
    ML_LLM_CODING = "ml_llm_coding"
    AGENT_RAG_TOOL_MEMORY = "agent_rag_tool_memory"
    PROJECT_DRILLDOWN = "project_drilldown"


class ClassificationResult(BaseModel):
    primary_label: PostLabel = PostLabel.UNCLEAR
    keep_for_extraction: bool = False
    confidence: float = 0.0
    reasons: list[str] = Field(default_factory=list)
    review_needed: bool = True
    company_name: str | None = None
    role_name: str | None = None


class ExtractedQuestion(BaseModel):
    raw_text: str
    question_type: QuestionType
    evidence_span: str | None = None


class ExtractionResult(BaseModel):
    company_name: str | None = None
    role_name: str | None = None
    interview_stage: str | None = None
    is_real_experience_confidence: float = 0.0
    questions: list[ExtractedQuestion] = Field(default_factory=list)


class MergeDecision(BaseModel):
    is_same_question: bool = False
    confidence: float = 0.0
    reason: str = ""


class CrawlPostImage(BaseModel):
    image_index: int
    image_url: str
    local_path: str | None = None
    sha256: str | None = None


class CrawlPostRecord(BaseModel):
    source_note_id: str
    note_url: str | None = None
    xsec_token: str | None = None
    xsec_source: str | None = None
    note_type: str | None = None
    title: str | None = None
    content: str | None = None
    author_id: str | None = None
    author_nickname: str | None = None
    author_avatar: str | None = None
    ip_location: str | None = None
    like_count: int | None = None
    collect_count: int | None = None
    comment_count: int | None = None
    share_count: int | None = None
    published_at: str | None = None
    raw_note_json: dict[str, Any]
    merged_text: str
    images: list[CrawlPostImage] = Field(default_factory=list)
