import asyncio
import time
from dataclasses import dataclass

import httpx

import config


@dataclass
class CallResult:
    text: str | None
    latency_s: float
    error: str | None
    input_tokens: int | None = None
    output_tokens: int | None = None


async def call_anthropic(model_id: str, prompt: str) -> CallResult:
    """product-service/app/services/ai_service.py의 _call_claude와 동일한 방식."""
    start = time.monotonic()
    if not config.ANTHROPIC_API_KEY:
        return CallResult(None, 0.0, "ANTHROPIC_API_KEY 없음")
    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            resp = await client.post(
                "https://api.anthropic.com/v1/messages",
                headers={
                    "x-api-key": config.ANTHROPIC_API_KEY,
                    "anthropic-version": "2023-06-01",
                    "content-type": "application/json",
                },
                json={
                    "model": model_id,
                    "max_tokens": 300,
                    "messages": [{"role": "user", "content": prompt}],
                },
            )
            resp.raise_for_status()
            data = resp.json()
        text = data["content"][0]["text"].strip()
        usage = data.get("usage", {})
        return CallResult(text, time.monotonic() - start, None, usage.get("input_tokens"), usage.get("output_tokens"))
    except Exception as e:  # noqa: BLE001 - 비교 도구라 모델별 실패를 넘기지 않고 결과에 기록
        return CallResult(None, time.monotonic() - start, str(e))


def _bedrock_converse_sync(model_id: str, prompt: str) -> dict:
    import boto3

    client = boto3.client("bedrock-runtime", region_name=config.AWS_REGION)
    return client.converse(
        modelId=model_id,
        messages=[{"role": "user", "content": [{"text": prompt}]}],
        inferenceConfig={"maxTokens": 300},
    )


async def call_bedrock(model_id: str, prompt: str) -> CallResult:
    """Converse API는 Bedrock에 올라간 모델군(Claude/Llama/Nova/Titan 등)에
    상관없이 같은 요청/응답 형식을 쓴다 - 모델별로 프롬프트 포맷을 따로 만들
    필요가 없다. boto3는 동기 SDK라 스레드로 돌린다."""
    start = time.monotonic()
    try:
        response = await asyncio.to_thread(_bedrock_converse_sync, model_id, prompt)
        text = response["output"]["message"]["content"][0]["text"].strip()
        usage = response.get("usage", {})
        return CallResult(
            text,
            time.monotonic() - start,
            None,
            usage.get("inputTokens"),
            usage.get("outputTokens"),
        )
    except Exception as e:  # noqa: BLE001
        return CallResult(None, time.monotonic() - start, str(e))


async def call_openai(model_id: str, prompt: str) -> CallResult:
    start = time.monotonic()
    if not config.OPENAI_API_KEY:
        return CallResult(None, 0.0, "OPENAI_API_KEY 없음")
    try:
        from openai import AsyncOpenAI

        client = AsyncOpenAI(api_key=config.OPENAI_API_KEY)
        resp = await client.chat.completions.create(
            model=model_id,
            max_tokens=300,
            messages=[{"role": "user", "content": prompt}],
        )
        text = (resp.choices[0].message.content or "").strip()
        usage = resp.usage
        return CallResult(
            text,
            time.monotonic() - start,
            None,
            usage.prompt_tokens if usage else None,
            usage.completion_tokens if usage else None,
        )
    except Exception as e:  # noqa: BLE001
        return CallResult(None, time.monotonic() - start, str(e))


async def call_gemini(model_id: str, prompt: str) -> CallResult:
    start = time.monotonic()
    if not config.GEMINI_API_KEY:
        return CallResult(None, 0.0, "GEMINI_API_KEY 없음")
    try:
        from google import genai

        client = genai.Client(api_key=config.GEMINI_API_KEY)
        resp = await client.aio.models.generate_content(model=model_id, contents=prompt)
        text = (resp.text or "").strip()
        usage = getattr(resp, "usage_metadata", None)
        return CallResult(
            text,
            time.monotonic() - start,
            None,
            getattr(usage, "prompt_token_count", None) if usage else None,
            getattr(usage, "candidates_token_count", None) if usage else None,
        )
    except Exception as e:  # noqa: BLE001
        return CallResult(None, time.monotonic() - start, str(e))


CALLERS = {
    "anthropic": call_anthropic,
    "bedrock": call_bedrock,
    "openai": call_openai,
    "gemini": call_gemini,
}
