from app.rag.ingest.load_rag_docs import build_rows, chunk_text


def test_chunk_text_still_works():
    # Task 12 기존 동작 회귀
    chunks = chunk_text("문단1.\n\n문단2.")
    assert chunks == ["문단1.", "문단2."]


def test_build_rows_pairs_chunks_and_vectors():
    chunks = ["무당류 기준", "WHO 당 권고"]
    vectors = [[0.1] * 1024, [0.2] * 1024]
    rows = build_rows(doc_name="who.md", source="WHO", chunks=chunks, vectors=vectors)
    assert len(rows) == 2
    assert rows[0]["chunk_text"] == "무당류 기준"
    assert rows[0]["source"] == "WHO"
    assert rows[0]["doc_name"] == "who.md"
    assert len(rows[0]["embedding"]) == 1024


def test_build_rows_mismatch_raises():
    import pytest
    with pytest.raises(ValueError):
        build_rows(doc_name="x", source="y", chunks=["a", "b"], vectors=[[0.1] * 1024])
