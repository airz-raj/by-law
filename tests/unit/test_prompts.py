from app.services.prompts import PROMPT_VERSION, BASE_SYSTEM_INSTRUCTION
from app.services.llm_schemas import NoticeExtraction

def test_prompts_exist():
    assert PROMPT_VERSION == "2026-09-a"
    assert "Indian legal AI assistant" in BASE_SYSTEM_INSTRUCTION

def test_schemas_can_instantiate():
    # Just to ensure schemas are valid pydantic models
    extraction = NoticeExtraction(
        sender_name="John",
        recipient_name="Jane",
        dates_found=[],
        demands=[],
        stated_deadline_days=None,
        stated_deadline_date=None
    )
    assert extraction.sender_name == "John"
