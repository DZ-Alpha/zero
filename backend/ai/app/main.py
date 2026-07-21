import logging
import time

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

logger = logging.getLogger("ai_service")

app = FastAPI(title="AI Service")

app.add_middleware(
    CORSMiddleware,
    allow_origins=[settings.frontend_url],
    allow_methods=["GET", "POST", "PUT", "DELETE"],
    allow_headers=["*"],
)


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
    engine = create_async_engine(settings.database_url)
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
        Intent.PRODUCT_ANALYSIS: ProductAnalysisHandler(),
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
