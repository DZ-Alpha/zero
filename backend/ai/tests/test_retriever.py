from app.rag.retriever import RagChunk, blocks_to_text


def test_blocks_to_text_joins_chunks():
    chunks = [
        RagChunk(text="무당류는 100g당 0.5g 미만", source="식약처 고시", score=0.9),
        RagChunk(text="WHO 당 10% 미만", source="WHO", score=0.8),
    ]
    text = blocks_to_text(chunks)
    assert "0.5g 미만" in text
    assert "WHO" in text


def test_blocks_to_text_empty_is_blank():
    assert blocks_to_text([]) == ""
