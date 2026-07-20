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
        return self.embed_batch([text], input_type="search_query")[0]
