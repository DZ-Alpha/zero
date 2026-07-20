from abc import ABC, abstractmethod
from collections.abc import Callable
from typing import Any

from pydantic import BaseModel
from sqlalchemy import text as sql_text


class RagChunk(BaseModel):
    text: str
    source: str
    score: float


class Retriever(ABC):
    @abstractmethod
    async def search_docs(self, query: str, k: int = 4) -> list[RagChunk]:
        ...

    @abstractmethod
    async def search_products(self, query: str, k: int = 4) -> list[RagChunk]:
        ...


def blocks_to_text(chunks: list[RagChunk]) -> str:
    if not chunks:
        return ""
    return "\n".join(f"- {c.text} (출처: {c.source})" for c in chunks)


class EmbeddingClient(ABC):
    @abstractmethod
    async def embed(self, text: str) -> list[float]:
        ...


class PgvectorRetriever(Retriever):
    """pgvector 코사인거리(<=>) top-k 검색. docs/products 테이블 분리.

    주의: docs_table/products_table은 원격 `service` 스키마가 아닌
    별도 `ai_rag` 스키마의 테이블을 가리켜야 한다. 이 클래스는 DDL을
    수행하지 않으며, 테이블이 이미 존재한다고 가정한다.
    """

    def __init__(self, session_factory: Callable[[], Any], embedder: EmbeddingClient,
                 docs_table: str = "ai_rag.rag_documents",
                 products_table: str = "service.product_embeddings") -> None:
        self._session_factory = session_factory
        self._embedder = embedder
        self._docs_table = docs_table
        self._products_table = products_table

    async def _search(self, table: str, query: str, k: int) -> list[RagChunk]:
        vector = await self._embedder.embed(query)
        stmt = sql_text(
            f"SELECT chunk_text, source, 1 - (embedding <=> :vec) AS score "
            f"FROM {table} ORDER BY embedding <=> :vec LIMIT :k"
        )
        async with self._session_factory() as session:
            rows = (await session.execute(stmt, {"vec": str(vector), "k": k})).all()
        return [RagChunk(text=r[0], source=r[1], score=float(r[2])) for r in rows]

    async def search_docs(self, query: str, k: int = 4) -> list[RagChunk]:
        return await self._search(self._docs_table, query, k)

    async def search_products(self, query: str, k: int = 4) -> list[RagChunk]:
        return await self._search(self._products_table, query, k)
