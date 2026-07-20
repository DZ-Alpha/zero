from app.rag.ingest.load_rag_docs import chunk_text


def test_chunk_splits_long_text():
    text = "문단1 내용.\n\n문단2 내용.\n\n" + "가" * 600
    chunks = chunk_text(text, max_chars=500)
    assert len(chunks) >= 2
    assert all(len(c) <= 500 for c in chunks)


def test_chunk_short_text_single():
    chunks = chunk_text("짧은 문장.", max_chars=500)
    assert chunks == ["짧은 문장."]


def test_pgvector_retriever_default_tables():
    from app.rag.retriever import PgvectorRetriever

    class _E:
        async def embed(self, text):
            return [0.0] * 1024

    r = PgvectorRetriever(session_factory=lambda: None, embedder=_E())
    assert r._docs_table == "ai_rag.rag_documents"
    assert r._products_table == "service.product_embeddings"
