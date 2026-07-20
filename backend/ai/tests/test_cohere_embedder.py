import json

from app.rag.ingest.cohere_embedder import CohereEmbedder


class _FakeBedrock:
    def __init__(self):
        self.last_body = None

    def invoke_model(self, modelId, body, contentType, accept):
        self.last_body = json.loads(body)
        n = len(self.last_body["texts"])
        # 1024차원 더미 벡터 n개 반환
        payload = {"embeddings": {"float": [[0.1] * 1024 for _ in range(n)]}}
        return {"body": _FakeStream(json.dumps(payload))}


class _FakeStream:
    def __init__(self, s): self._s = s.encode()
    def read(self): return self._s


def test_embed_batch_builds_correct_request():
    fake = _FakeBedrock()
    embedder = CohereEmbedder(region="ap-northeast-2", client=fake)
    vectors = embedder.embed_batch(["무당류 기준", "WHO 당 권고"], input_type="search_document")
    assert len(vectors) == 2
    assert len(vectors[0]) == 1024
    assert fake.last_body["input_type"] == "search_document"
    assert fake.last_body["output_dimension"] == 1024
    assert fake.last_body["texts"] == ["무당류 기준", "WHO 당 권고"]


async def test_embed_single_uses_search_query():
    fake = _FakeBedrock()
    embedder = CohereEmbedder(region="ap-northeast-2", client=fake)
    vec = await embedder.embed("무설탕이면 열량도 0이야?")
    assert len(vec) == 1024
    assert fake.last_body["input_type"] == "search_query"


def test_embed_batch_chunks_over_96():
    fake = _FakeBedrock()
    embedder = CohereEmbedder(region="ap-northeast-2", client=fake)
    texts = [f"문장{i}" for i in range(100)]
    vectors = embedder.embed_batch(texts, input_type="search_document")
    assert len(vectors) == 100  # 96 + 4 두 배치로 나뉘어도 총 100개
