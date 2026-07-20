from abc import ABC, abstractmethod

import boto3

from app.core.config import settings


class LLMClient(ABC):
    @abstractmethod
    async def complete(self, system: str, user: str) -> str:
        ...


class BedrockClient(LLMClient):
    """AWS Bedrock converse API 래퍼. 모델ID는 settings에서 주입(PoC로 선정)."""

    def __init__(self, model_id: str | None = None) -> None:
        self._model_id = model_id or settings.bedrock_model_id
        if not self._model_id:
            raise ValueError("BEDROCK_MODEL_ID가 설정되지 않았습니다(PoC로 선정 후 .env에 지정).")
        self._client = boto3.client("bedrock-runtime", region_name=settings.bedrock_region)

    async def complete(self, system: str, user: str) -> str:
        # boto3는 동기 — 간단하게 호출한다. 부하가 커지면 스레드풀로 옮긴다.
        # maxTokens로 답변 길이를 제한한다(좁은 채팅창 + 응답 속도). 짧은 답이
        # 기본이지만 잘리지 않을 여유는 둔다.
        resp = self._client.converse(
            modelId=self._model_id,
            system=[{"text": system}],
            messages=[{"role": "user", "content": [{"text": user}]}],
            inferenceConfig={"maxTokens": 250},
        )
        return resp["output"]["message"]["content"][0]["text"]
