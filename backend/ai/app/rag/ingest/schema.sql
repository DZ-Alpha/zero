-- RAG 지식문서 전용 스키마. service 스키마(데이터팀 관리)와 완전 분리.
-- 서버 pgvector에 최초 1회 실행. pgvector 확장은 이미 설치되어 있다고 가정.
CREATE SCHEMA IF NOT EXISTS ai_rag;

CREATE TABLE IF NOT EXISTS ai_rag.rag_documents (
    id BIGSERIAL PRIMARY KEY,
    chunk_text TEXT NOT NULL,
    source TEXT NOT NULL,
    doc_name TEXT NOT NULL,
    embedding VECTOR(1024) NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_rag_documents_embedding
    ON ai_rag.rag_documents USING hnsw (embedding vector_cosine_ops);

CREATE INDEX IF NOT EXISTS idx_rag_documents_doc_name
    ON ai_rag.rag_documents (doc_name);
