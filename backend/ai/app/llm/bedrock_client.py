import asyncio
from abc import ABC, abstractmethod
from collections.abc import AsyncIterator

import boto3

from app.core.config import settings


class LLMClient(ABC):
    @abstractmethod
    async def complete(self, system: str, user: str) -> str:
        ...

    @abstractmethod
    def complete_stream(self, system: str, user: str) -> AsyncIterator[str]:
        ...


class BedrockClient(LLMClient):
    """AWS Bedrock converse API 래퍼. 모델ID는 settings에서 주입(PoC로 선정)."""

    def __init__(self, model_id: str | None = None, client=None) -> None:
        self._model_id = model_id or settings.bedrock_model_id
        if not self._model_id:
            raise ValueError("BEDROCK_MODEL_ID가 설정되지 않았습니다(PoC로 선정 후 .env에 지정).")
        self._client = client or boto3.client("bedrock-runtime", region_name=settings.bedrock_region)

    async def complete(self, system: str, user: str) -> str:
        # boto3는 동기 — 간단하게 호출한다. 부하가 커지면 스레드풀로 옮긴다.
        # maxTokens로 답변 길이를 제한한다(좁은 채팅창 + 응답 속도). 짧은 답이
        # 기본이지만 잘리지 않을 여유는 둔다.
        resp = self._client.converse(
            modelId=self._model_id,
            system=[{"text": system}],
            messages=[{"role": "user", "content": [{"text": user}]}],
            # 답변이 잘리지 않도록 넉넉히. 길이는 프롬프트(3문장 이내)로 조절한다.
            inferenceConfig={"maxTokens": 500},
        )
        return resp["output"]["message"]["content"][0]["text"]

    async def complete_stream(self, system: str, user: str) -> AsyncIterator[str]:
        # converse_stream은 동기 이터레이터를 반환한다. 이벤트 루프를 막지 않도록
        # 각 청크 획득을 asyncio.to_thread로 넘긴다.
        resp = await asyncio.to_thread(
            self._client.converse_stream,
            modelId=self._model_id,
            system=[{"text": system}],
            messages=[{"role": "user", "content": [{"text": user}]}],
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
