import logging
import time
# rebuild trigger — Harbor image re-push (2026-07-31 재배포)

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

logging.Formatter.converter = time.gmtime
logging.basicConfig(level=logging.INFO, format="%(asctime)sZ %(levelname)s %(name)s %(message)s")

from app.core.config import settings  # noqa: E402
from app.api import chatbot as chatbot_api  # noqa: E402
from app.context.provider import build_provider  # noqa: E402
from app.handlers.admin_analytics import AdminAnalyticsHandler  # noqa: E402
from app.handlers.diet_photo import DietPhotoHandler  # noqa: E402
from app.handlers.general_qa import GeneralQAHandler  # noqa: E402
from app.handlers.product_analysis import ProductAnalysisHandler  # noqa: E402
from app.handlers.recipe_substitute import RecipeSubstituteHandler  # noqa: E402
from app.handlers.recommend import RecommendHandler  # noqa: E402
from app.llm.bedrock_client import BedrockClient, LLMClient  # noqa: E402
from app.rag.retriever import RagChunk, Retriever  # noqa: E402
from app.router.dispatcher import Dispatcher  # noqa: E402
from app.router.intent import IntentClassifier  # noqa: E402
from app.schemas import Intent  # noqa: E402
from app.core.redis_client import redis_client  # noqa: E402
from app.memory.conversation_store import ConversationStore  # noqa: E402
from app.services.chat_photo_storage import ensure_lifecycle as ensure_chat_photo_lifecycle  # noqa: E402
from app.services.vision_analyzer import build_analyzer  # noqa: E402

logger = logging.getLogger("ai_service")

# /docs, /redoc, /openapi.json은 settings.enable_api_docs(기본 False)로 게이트한다
# - 자세한 이유는 app/core/config.py 주석 참고.
app = FastAPI(
    title="AI Service",
    docs_url="/docs" if settings.enable_api_docs else None,
    redoc_url="/redoc" if settings.enable_api_docs else None,
    openapi_url="/openapi.json" if settings.enable_api_docs else None,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=[settings.frontend_url],
    allow_methods=["GET", "POST", "PUT", "DELETE"],
    allow_headers=["*"],
)


@app.on_event("startup")
async def on_startup() -> None:
    # chat-photos 버킷에 24시간 만료 규칙이 있는지 보장 - MinIO 미설정/미기동이어도
    # 부가 기능이라 서비스 자체는 정상 기동한다(ensure_lifecycle 내부에서 처리).
    await ensure_chat_photo_lifecycle()


@app.exception_handler(Exception)
async def unhandled_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    logger.exception("unhandled error handling %s %s", request.method, request.url.path)
    return JSONResponse(status_code=500, content={"detail": "일시적인 오류가 발생했습니다. 잠시 후 다시 시도해주세요."})


class _NullRetriever(Retriever):
    # pgvector 실연결(Task 12) 전까지 빈 결과. 개인화·라우팅은 이걸로도 동작.
    async def search_docs(self, query: str, k: int = 4) -> list[RagChunk]:
        return []

    async def search_products(self, query: str, k: int = 4) -> list[RagChunk]:
        return []


def _build_llm() -> LLMClient | None:
    # 모델 미선정(PoC 전)이면 None — general_qa는 아직 실호출 못 하지만 서비스는 뜬다.
    if not settings.bedrock_model_id:
        return None
    return BedrockClient()


async def _llm_classify(msg: str) -> Intent:
    # 모델 선정 후 프롬프트 기반 분류로 교체. 그전까지는 일반질문으로 처리.
    return Intent.GENERAL_QA


def build_retriever() -> Retriever:
    # rag_enabled일 때만 실제 pgvector 검색. 아니면 빈 결과(다른 개발 환경 보호).
    if not settings.rag_enabled:
        return _NullRetriever()
    from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

    from app.rag.ingest.cohere_embedder import CohereEmbedder
    from app.rag.retriever import PgvectorRetriever
    # 이 Postgres 인스턴스는 다른 백엔드 서비스들과 공유한다 - 기본 풀 크기로
    # 여러 서비스가 동시에 접속하면 max_connections를 넘기기 쉽다
    # (2026-07-31 TooManyConnectionsError 재현). 접속 상한을 보수적으로 고정.
    engine = create_async_engine(
        settings.database_url,
        pool_size=5,
        max_overflow=3,
        pool_timeout=10,
        pool_recycle=1800,
        pool_pre_ping=True,
    )
    session_factory = async_sessionmaker(engine, expire_on_commit=False)
    embedder = CohereEmbedder(region=settings.embed_region)
    return PgvectorRetriever(
        session_factory=session_factory, embedder=embedder,
        docs_table="ai_rag.rag_documents", products_table="service.product_embeddings",
    )


def build_dependencies() -> chatbot_api.Dependencies:
    provider = build_provider(settings.user_context_source)
    classifier = IntentClassifier(llm_classify=_llm_classify)
    llm = _build_llm()
    retriever = build_retriever()
    handlers = {
        Intent.PRODUCT_ANALYSIS: ProductAnalysisHandler(
            analyzer=build_analyzer(settings),
            confidence_threshold=settings.vision_confidence_threshold,
        ),
        Intent.RECOMMEND: RecommendHandler(),
        Intent.DIET_PHOTO: DietPhotoHandler(),
        Intent.RECIPE_SUBSTITUTE: RecipeSubstituteHandler(),
        Intent.ADMIN_ANALYTICS: AdminAnalyticsHandler(),
    }
    qa = None
    if llm is not None:
        qa = GeneralQAHandler(llm=llm, retriever=retriever)
        handlers[Intent.GENERAL_QA] = qa
    store = ConversationStore(
        redis_client,
        max_turns=20,
        ttl_seconds=settings.conversation_ttl_seconds,
    )
    return chatbot_api.Dependencies(provider=provider, classifier=classifier,
                                    dispatcher=Dispatcher(handlers), qa_handler=qa,
                                    store=store)


app.include_router(chatbot_api.router)
chatbot_api.set_dependencies(build_dependencies())


@app.get("/health")
async def health() -> dict[str, str]:
    return {"status": "ok"}
