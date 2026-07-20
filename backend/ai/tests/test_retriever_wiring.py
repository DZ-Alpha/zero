from app.main import build_retriever
from app.rag.retriever import Retriever


def test_build_retriever_returns_retriever():
    # rag_enabled 기본 False → NullRetriever, 그래도 Retriever 타입이어야 함
    r = build_retriever()
    assert isinstance(r, Retriever)


async def test_null_retriever_returns_empty_when_rag_disabled():
    r = build_retriever()
    assert await r.search_docs("아무거나") == []
