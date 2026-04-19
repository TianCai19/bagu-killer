from __future__ import annotations

import logging
from dataclasses import dataclass

from ai_offer_catcher.artifacts import ArtifactStore
from ai_offer_catcher.models.schemas import MergeDecision
from ai_offer_catcher.utils import extract_first_json_object, render_prompt

logger = logging.getLogger(__name__)


@dataclass
class _CandidateDecision:
    candidate: dict
    merge_method: str
    merge_score: float | None
    review_needed: bool


class QuestionMergeStage:
    PROMPT_VERSION = "question_merge_v2"
    CANDIDATE_LIMIT = 12
    SEMANTIC_JUDGE_FLOOR = 0.72

    def __init__(self, repo, prompt_env, embed_model, judge_model, artifacts: ArtifactStore, similarity_threshold: float, review_threshold: float) -> None:
        self.repo = repo
        self.prompt_env = prompt_env
        self.embed_model = embed_model
        self.judge_model = judge_model
        self.artifacts = artifacts
        self.similarity_threshold = similarity_threshold
        self.review_threshold = review_threshold

    def run(self, limit: int) -> int:
        processed = 0
        for row in self.repo.list_questions_for_merge(limit):
            fingerprint_match = self.repo.find_canonical_by_fingerprint(row["fingerprint"], row["question_type"])
            if fingerprint_match:
                self.repo.link_question(
                    raw_post_id=row["raw_post_id"],
                    extracted_question_id=row["id"],
                    canonical_question_id=fingerprint_match["id"],
                    alias_text=row["raw_text"],
                    normalized_text=row["normalized_text"],
                    fingerprint=row["fingerprint"],
                    merge_method="fingerprint",
                    merge_score=1.0,
                    review_needed=False,
                    company_name=row.get("company_name"),
                    role_name=row.get("role_name"),
                    interview_stage=row.get("interview_stage"),
                )
                processed += 1
                continue

            embedding = self.embed_model.encode([row["normalized_text"]])[0]
            candidates = self.repo.search_similar_canonicals(embedding, row["question_type"], limit=self.CANDIDATE_LIMIT)

            chosen = None
            merge_method = "new"
            review_needed = False
            merge_score = None
            chosen_decision = self._choose_candidate(row, candidates)
            if chosen_decision is not None:
                chosen = chosen_decision.candidate
                merge_method = chosen_decision.merge_method
                merge_score = chosen_decision.merge_score
                review_needed = chosen_decision.review_needed

            if chosen is None:
                chosen = self.repo.insert_canonical_question(
                    canonical_text=row["raw_text"],
                    normalized_text=row["normalized_text"],
                    fingerprint=row["fingerprint"],
                    question_type=row["question_type"],
                    embedding=embedding,
                    first_seen_post_id=row["raw_post_id"],
                )
                merge_method = "new_canonical"

            self.repo.link_question(
                raw_post_id=row["raw_post_id"],
                extracted_question_id=row["id"],
                canonical_question_id=chosen["id"],
                alias_text=row["raw_text"],
                normalized_text=row["normalized_text"],
                fingerprint=row["fingerprint"],
                merge_method=merge_method,
                merge_score=merge_score,
                review_needed=review_needed,
                company_name=row.get("company_name"),
                role_name=row.get("role_name"),
                interview_stage=row.get("interview_stage"),
            )
            processed += 1
        return processed

    def _choose_candidate(self, row: dict, candidates: list[dict]) -> _CandidateDecision | None:
        semantic_candidates: list[tuple[dict, float]] = []
        for candidate in candidates:
            similarity = float(candidate.get("similarity") or 0.0)
            if similarity >= self.similarity_threshold:
                return _CandidateDecision(
                    candidate=candidate,
                    merge_method="embedding_threshold",
                    merge_score=similarity,
                    review_needed=False,
                )
            if similarity >= min(self.review_threshold, self.SEMANTIC_JUDGE_FLOOR):
                semantic_candidates.append((candidate, similarity))

        best_match: _CandidateDecision | None = None
        best_confidence = -1.0
        for candidate, similarity in semantic_candidates:
            decision = self._judge(
                row["normalized_text"],
                candidate["normalized_text"],
                row["id"],
                candidate["id"],
            )
            if not decision.is_same_question:
                continue
            confidence = float(decision.confidence or 0.0)
            review_needed = confidence < 0.85 or similarity < self.similarity_threshold
            candidate_decision = _CandidateDecision(
                candidate=candidate,
                merge_method="llm_judge",
                merge_score=similarity,
                review_needed=review_needed,
            )
            if confidence > best_confidence:
                best_match = candidate_decision
                best_confidence = confidence
        return best_match

    def _judge(self, left_question: str, right_question: str, left_id: int, right_id: int) -> MergeDecision:
        prompt = render_prompt(
            self.prompt_env,
            "question_merge.jinja2",
            left_question=left_question,
            right_question=right_question,
        )
        raw_output = self.judge_model.generate(prompt)
        try:
            payload = extract_first_json_object(raw_output)
            result = MergeDecision.model_validate(payload)
        except Exception:
            payload = {"raw_output": raw_output}
            result = MergeDecision()
        self.artifacts.write_json(
            f"merge/judge_{left_id}_{right_id}.json",
            {"prompt": prompt, "raw_output": raw_output, "parsed": payload},
        )
        return result
