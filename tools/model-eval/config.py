import os
from dataclasses import dataclass

from dotenv import load_dotenv

load_dotenv()


@dataclass(frozen=True)
class ModelCandidate:
    provider: str  # "anthropic" | "bedrock" | "openai" | "gemini"
    model_id: str
    label: str  # 결과 표에 찍힐 이름


# NOTE: provider="bedrock" 항목의 model_id는 리전/계정마다 사용 가능 여부와
# 정확한 버전 문자열이 달라진다 - 여기 적힌 값은 예시일 뿐이니, 실행 전에
# `aws bedrock list-foundation-models --region $AWS_REGION` 이나 콘솔에서
# 실제 활성화된 model id로 맞춰 넣어야 한다. openai/gemini 쪽 모델명도 계정의
# 접근 권한에 따라 달라질 수 있으니 마찬가지로 확인 후 조정할 것.
CANDIDATES: list[ModelCandidate] = [
    # --- Anthropic 다이렉트 (지금 product-service가 실제로 쓰는 방식) ---
    ModelCandidate("anthropic", "claude-haiku-4-5-20251001", "Anthropic/Haiku4.5"),
    ModelCandidate("anthropic", "claude-sonnet-5", "Anthropic/Sonnet5"),
    ModelCandidate("anthropic", "claude-opus-4-8", "Anthropic/Opus4.8"),

    # --- AWS Bedrock (Converse API로 호출 - 모델군 상관없이 동일 인터페이스) ---
    # 확인 필요: 아래 model id들은 예시. 실제 계정에서 활성화된 정확한 id로 교체할 것.
    ModelCandidate("bedrock", "anthropic.claude-opus-4-8-v1:0", "Bedrock/Claude-Opus4.8"),
    ModelCandidate("bedrock", "meta.llama3-3-70b-instruct-v1:0", "Bedrock/Llama3.3-70B"),
    ModelCandidate("bedrock", "amazon.nova-pro-v1:0", "Bedrock/Nova-Pro"),
    ModelCandidate("bedrock", "amazon.titan-text-premier-v1:0", "Bedrock/Titan-Premier"),

    # --- OpenAI ---
    # 확인 필요: 계정에서 실제 접근 가능한 모델명으로 교체할 것.
    ModelCandidate("openai", "gpt-5.1", "OpenAI/GPT-5.1"),

    # --- Google Gemini ---
    # 확인 필요: 계정에서 실제 접근 가능한 모델명으로 교체할 것.
    ModelCandidate("gemini", "gemini-3-pro", "Gemini/3-Pro"),
]

POSTGRES_HOST = os.getenv("POSTGRES_HOST", "localhost")
POSTGRES_PORT = int(os.getenv("POSTGRES_PORT", "5432"))
POSTGRES_DB = os.getenv("POSTGRES_DB", "test_db")
POSTGRES_USER = os.getenv("POSTGRES_USER", "")
POSTGRES_PASSWORD = os.getenv("POSTGRES_PASSWORD", "")

ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY", "")
AWS_REGION = os.getenv("AWS_REGION", "us-east-1")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "")
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "")

EVAL_SAMPLE_SIZE = int(os.getenv("EVAL_SAMPLE_SIZE", "5"))

# PR-0303(사용자 맞춤 설명) 테스트용 - 실제 유저 건강정보를 이 도구에 끌어오지
# 않기 위해 대표 프로필 2개를 고정값으로 둔다(실제 서비스는 매번 다른 사용자
# 데이터를 쓰지만, 여기선 모델 비교가 목적이라 입력을 고정해야 결과 비교가 됨).
SAMPLE_USER_PROFILES = [
    {"label": "30대 여성", "birth_year": 1994, "gender": "F", "daily_calorie_target": 1800.0, "daily_sugar_target_g": 25.0},
    {"label": "20대 남성", "birth_year": 2001, "gender": "M", "daily_calorie_target": 2400.0, "daily_sugar_target_g": 36.0},
]
