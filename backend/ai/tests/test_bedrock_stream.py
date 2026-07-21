import pytest

from app.llm.bedrock_client import BedrockClient


class _FakeStreamClient:
    """converse_stream을 흉내내는 페이크. 동기 이터레이터 stream을 반환."""
    def __init__(self, deltas):
        self._deltas = deltas
        self.last_kwargs = None

    def converse_stream(self, **kwargs):
        self.last_kwargs = kwargs
        events = [{"contentBlockDelta": {"delta": {"text": d}}} for d in self._deltas]
        # 텍스트 없는 이벤트(messageStart 등)도 섞여 올 수 있음 — 무시돼야 함
        events = [{"messageStart": {"role": "assistant"}}] + events + [{"messageStop": {}}]
        return {"stream": iter(events)}


async def test_complete_stream_yields_text_deltas_in_order():
    fake = _FakeStreamClient(["탄수화물은", " 에너지원", "이에요"])
    client = BedrockClient(model_id="m", client=fake)
    out = []
    async for delta in client.complete_stream("시스템", "질문"):
        out.append(delta)
    assert out == ["탄수화물은", " 에너지원", "이에요"]


async def test_complete_stream_sends_system_and_user():
    fake = _FakeStreamClient(["ok"])
    client = BedrockClient(model_id="m", client=fake)
    async for _ in client.complete_stream("SYS", "USR"):
        pass
    assert fake.last_kwargs["system"] == [{"text": "SYS"}]
    assert fake.last_kwargs["messages"] == [{"role": "user", "content": [{"text": "USR"}]}]
    assert fake.last_kwargs["modelId"] == "m"
