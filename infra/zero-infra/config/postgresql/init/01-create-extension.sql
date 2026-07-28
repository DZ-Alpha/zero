CREATE EXTENSION IF NOT EXISTS vector;

CREATE TABLE IF NOT EXISTS service.product_embeddings (
    product_id  UUID PRIMARY KEY REFERENCES service.products(product_id) ON DELETE CASCADE,
    embedding   VECTOR(1024) NOT NULL,
    source_text TEXT,
    updated_at  TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS product_embeddings_embedding_idx
    ON service.product_embeddings USING hnsw (embedding vector_cosine_ops);
