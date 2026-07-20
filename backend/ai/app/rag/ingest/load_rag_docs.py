"""식약처/WHO/KDRIs 문서를 청크·임베딩해 pgvector(ai_rag 스키마)에 적재.

실행: python -m app.rag.ingest.load_rag_docs <문서파일.md> <출처명>
DDL은 service 스키마가 아닌 ai_rag 전용 스키마에만 수행한다(schema.sql).
서버 pgvector에 SSH 터널로 연결해 실행하며, 실행 전 사용자 승인을 받는다.
"""
import os
import sys


def chunk_text(text: str, max_chars: int = 500) -> list[str]:
    chunks: list[str] = []
    for para in (p.strip() for p in text.split("\n\n")):
        if not para:
            continue
        if len(para) <= max_chars:
            chunks.append(para)
        else:
            for i in range(0, len(para), max_chars):
                chunks.append(para[i:i + max_chars])
    return chunks


def build_rows(doc_name: str, source: str, chunks: list[str],
               vectors: list[list[float]]) -> list[dict]:
    if len(chunks) != len(vectors):
        raise ValueError(f"청크 수({len(chunks)})와 벡터 수({len(vectors)})가 다릅니다.")
    return [
        {"chunk_text": c, "source": source, "doc_name": doc_name, "embedding": v}
        for c, v in zip(chunks, vectors)
    ]


def ingest_file(path: str, source: str, embedder, conn_factory) -> int:
    """파일 하나를 적재. doc_name 기준 멱등(기존 삭제 후 삽입). 삽입 행 수 반환."""
    doc_name = os.path.basename(path)
    with open(path, encoding="utf-8") as f:
        chunks = chunk_text(f.read())
    if not chunks:
        return 0
    vectors = embedder.embed_batch(chunks, input_type="search_document")
    rows = build_rows(doc_name, source, chunks, vectors)

    with conn_factory() as conn:
        with conn.cursor() as cur:
            cur.execute("DELETE FROM ai_rag.rag_documents WHERE doc_name = %s", (doc_name,))
            for r in rows:
                vec_literal = "[" + ",".join(str(x) for x in r["embedding"]) + "]"
                cur.execute(
                    "INSERT INTO ai_rag.rag_documents (chunk_text, source, doc_name, embedding) "
                    "VALUES (%s, %s, %s, %s::vector)",
                    (r["chunk_text"], r["source"], r["doc_name"], vec_literal),
                )
        conn.commit()
    return len(rows)


def main() -> None:
    if len(sys.argv) < 3:
        print("사용법: python -m app.rag.ingest.load_rag_docs <문서.md> <출처명>")
        raise SystemExit(1)
    import psycopg
    from app.core.config import settings
    from app.rag.ingest.cohere_embedder import CohereEmbedder

    path, source = sys.argv[1], sys.argv[2]
    embedder = CohereEmbedder(region=settings.embed_region)
    # psycopg 동기 연결 — 적재는 배치 1회성이라 async 불필요.
    dsn = settings.database_url.replace("+asyncpg", "")
    n = ingest_file(path, source, embedder, lambda: psycopg.connect(dsn))
    print(f"{source} ({os.path.basename(path)}): {n}개 청크 적재 완료.")


if __name__ == "__main__":
    main()
