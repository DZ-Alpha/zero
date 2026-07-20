from app.llm.prompts import SYSTEM_PROMPT_QA, build_qa_user_prompt


def test_system_prompt_has_antihallucination_rules():
    # 설계 §5·PoC 원칙: 제공된 정보만 근거, 없으면 지어내지 말 것.
    assert "지어내지" in SYSTEM_PROMPT_QA or "추측" in SYSTEM_PROMPT_QA


def test_system_prompt_marks_estimates_and_defers_to_experts():
    # 권장 칼로리·당류는 공식 추정치임을 밝히고 전문가 상담을 안내해야 한다.
    assert "추정치" in SYSTEM_PROMPT_QA
    assert "전문가" in SYSTEM_PROMPT_QA


def test_system_prompt_no_allergy_verdict_before_checking():
    # 알레르기: 구체 성분 확인 전에는 섭취 가부를 단정하지 말 것(PoC c6 Nova Lite 사례).
    assert "알레르기" in SYSTEM_PROMPT_QA
    assert "단정" in SYSTEM_PROMPT_QA


def test_build_user_prompt_includes_all_blocks():
    prompt = build_qa_user_prompt(
        msg="이 초코바 먹어도 돼?",
        user_context_block="하루 당 목표 48g",
        rag_block="식약처: 무당류는 100g당 0.5g 미만",
        product_block="초코바 당류 20g",
    )
    assert "이 초코바 먹어도 돼?" in prompt
    assert "48g" in prompt
    assert "0.5g 미만" in prompt
    assert "20g" in prompt


def test_build_user_prompt_handles_empty_blocks():
    prompt = build_qa_user_prompt(msg="탄수화물이 뭐야?", user_context_block="",
                                  rag_block="", product_block="")
    assert "탄수화물이 뭐야?" in prompt
