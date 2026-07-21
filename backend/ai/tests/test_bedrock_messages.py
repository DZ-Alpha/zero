import pytest

from app.llm.bedrock_client import BedrockClient


class _FakeBoto:
    def __init__(self):
        self.captured = None

    def converse(self, **kwargs):
        self.captured = kwargs
        return {"output": {"message": {"content": [{"text": "응답"}]}}}


def _client(fake):
    return BedrockClient(model_id="test-model", client=fake)


async def test_complete_converts_messages_to_converse_format():
    fake = _FakeBoto()
    client = _client(fake)
    msgs = [
        {"role": "user", "text": "나 알레르기 있어"},
        {"role": "assistant", "text": "어떤 성분요?"},
        {"role": "user", "text": "땅콩"},
    ]
    out = await client.complete("시스템", msgs)
    assert out == "응답"
    sent = fake.captured["messages"]
    assert sent == [
        {"role": "user", "content": [{"text": "나 알레르기 있어"}]},
        {"role": "assistant", "content": [{"text": "어떤 성분요?"}]},
        {"role": "user", "content": [{"text": "땅콩"}]},
    ]
    assert fake.captured["system"] == [{"text": "시스템"}]
