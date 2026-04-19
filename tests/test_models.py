from ai_offer_catcher.models.schemas import ClassificationResult, ExtractionResult, PostLabel, QuestionType


def test_classification_defaults_are_safe():
    result = ClassificationResult()
    assert result.primary_label == PostLabel.UNCLEAR
    assert result.keep_for_extraction is False


def test_extraction_accepts_questions():
    result = ExtractionResult.model_validate(
        {
            "company_name": "OpenAI",
            "questions": [
                {"raw_text": "什么是 tool calling", "question_type": QuestionType.AGENT_RAG_TOOL_MEMORY}
            ],
        }
    )
    assert result.questions[0].raw_text == "什么是 tool calling"
