import asyncio
from abc import ABC, abstractmethod
from collections.abc import AsyncIterator

import boto3

from app.core.config import settings


def _to_converse(messages: list[dict]) -> list[dict]:
    # {"role","text"} → Bedrock converse {"role","content":[{"text"}]}
    return [{"role": m["role"], "content": [{"text": m["text"]}]} for m in messages]


class LLMClient(ABC):
    @abstractmethod
    async def complete(self, system: str, messages: list[dict]) -> str:
        ...

    @abstractmethod
    def complete_stream(self, system: str, messages: list[dict]) -> AsyncIterator[str]:
        ...


class BedrockClient(LLMClient):
    """AWS Bedrock converse API 래퍼. 모델ID는 settings에서 주입(PoC로 선정)."""

    def __init__(self, model_id: str | None = None, client=None) -> None:
        self._model_id = model_id or settings.bedrock_model_id
        if not self._model_id:
            raise ValueError("BEDROCK_MODEL_ID가 설정되지 않았습니다(PoC로 선정 후 .env에 지정).")
        self._client = client or boto3.client("bedrock-runtime", region_name=settings.bedrock_region)

    async def complete(self, system: str, messages: list[dict]) -> str:
        resp = self._client.converse(
            modelId=self._model_id,
            system=[{"text": system}],
            messages=_to_converse(messages),
            inferenceConfig={"maxTokens": 500},
        )
        return resp["output"]["message"]["content"][0]["text"]

    async def complete_stream(self, system: str, messages: list[dict]) -> AsyncIterator[str]:
        resp = await asyncio.to_thread(
            self._client.converse_stream,
            modelId=self._model_id,
            system=[{"text": system}],
            messages=_to_converse(messages),
            inferenceConfig={"maxTokens": 500},
        )
        stream = resp["stream"]
        it = iter(stream)
        _SENTINEL = object()
        while True:
            event = await asyncio.to_thread(next, it, _SENTINEL)
            if event is _SENTINEL:
                break
            delta = event.get("contentBlockDelta", {}).get("delta", {}).get("text")
            if delta:
                yield delta
