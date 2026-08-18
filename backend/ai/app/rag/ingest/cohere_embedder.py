import asyncio
import json

import boto3

from app.rag.retriever import EmbeddingClient

MODEL_ID = "global.cohere.embed-v4:0"
DIMENSIONS = 1024
BATCH = 96


class CohereEmbedder(EmbeddingClient):
    """Bedrock Cohere Embed v4 래퍼. 적재는 search_document, 검색은 search_query."""

    def __init__(self, region: str, model_id: str = MODEL_ID, dimensions: int = DIMENSIONS, client=None) -> None:
        self._model_id = model_id
        self._dimensions = dimensions
        self._client = client or boto3.client("bedrock-runtime", region_name=region)

    def embed_batch(self, texts: list[str], input_type: str) -> list[list[float]]:
        out: list[list[float]] = []
        for i in range(0, len(texts), BATCH):
            batch = texts[i:i + BATCH]
            body = json.dumps({
                "texts": batch, "input_type": input_type,
                "embedding_types": ["float"], "output_dimension": self._dimensions,
            })
            resp = self._client.invoke_model(
                modelId=self._model_id, body=body,
                contentType="application/json", accept="application/json",
            )
            result = json.loads(resp["body"].read())
            out.extend(result["embeddings"]["float"])
        return out

    async def embed(self, text: str) -> list[float]:
        # 검색 경로 — 단건, search_query.
        # embed_batch 안의 invoke_model은 boto3(동기)라, ai-service(uvicorn 단일
        # 워커)에서 await 없이 부르면 임베딩 왕복 동안 이벤트 루프 전체가 멈춘다
        # (2026-07-31 diet/product에서 고친 것과 같은 사고). to_thread로 위임한다.
        # embed_batch 자체는 동기로 둔다 - 적재 스크립트(load_rag_docs.py)가
        # 동기 컨텍스트에서 그대로 부른다.
        vectors = await asyncio.to_thread(self.embed_batch, [text], input_type="search_query")
        return vectors[0]
