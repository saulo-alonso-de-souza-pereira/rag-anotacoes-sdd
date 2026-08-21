from collections.abc import AsyncIterator, Awaitable, Callable
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import APIRouter, FastAPI
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from notes_rag.api.auth import router as auth_router
from notes_rag.api.chat import router as chat_router
from notes_rag.api.errors import install_error_handlers
from notes_rag.api.notes import router as notes_router
from notes_rag.config import Settings, get_settings
from notes_rag.llm.ollama import OllamaClient
from notes_rag.persistence.database import create_runtime_engine, create_session_factory
from notes_rag.runtime import (
    RetryGateway,
    authentication_service,
    note_service,
    rag_service,
    retrieval_service,
)

ReadyProbe = Callable[[], Awaitable[bool]]


async def always_ready() -> bool:
    return True


def create_app(
    settings: Settings | None = None,
    *,
    database_probe: ReadyProbe = always_ready,
    model_probe: ReadyProbe = always_ready,
) -> FastAPI:
    resolved_settings = settings

    @asynccontextmanager
    async def lifespan(app: FastAPI) -> AsyncIterator[None]:
        app.state.settings = resolved_settings or get_settings()
        configuration = app.state.settings
        engine = create_runtime_engine(configuration)
        sessions = create_session_factory(engine)
        ollama = OllamaClient(
            str(configuration.ollama_url),
            embedding_model=configuration.embedding_model,
            generation_model=configuration.generation_model,
        )
        if not hasattr(app.state, "auth_service"):
            app.state.auth_service = authentication_service(sessions, configuration)
        if not hasattr(app.state, "note_service_factory"):
            app.state.note_service_factory = lambda user_id: note_service(sessions, user_id)
        if not hasattr(app.state, "retrieval_service_factory"):
            app.state.retrieval_service_factory = lambda user_id: retrieval_service(
                sessions, ollama, user_id, configuration
            )
        if not hasattr(app.state, "indexing_repository_factory"):
            app.state.indexing_repository_factory = lambda _user_id: RetryGateway(sessions)
        if not hasattr(app.state, "rag_service_factory"):
            app.state.rag_service_factory = lambda user_id: rag_service(
                sessions, ollama, user_id, configuration
            )
        try:
            yield
        finally:
            await ollama.close()
            await engine.dispose()

    app = FastAPI(
        title="Personal Notes RAG API",
        version="1.0.0",
        docs_url="/api/docs",
        openapi_url="/api/openapi.json",
        lifespan=lifespan,
    )
    install_error_handlers(app)

    router = APIRouter(prefix="/api/v1")
    router.include_router(auth_router)
    router.include_router(notes_router)
    router.include_router(chat_router)

    @router.get("/health/live", include_in_schema=False)
    async def live() -> dict[str, str]:
        return {"status": "ok"}

    @router.get("/health/ready", include_in_schema=False)
    async def ready() -> tuple[dict[str, str], int] | dict[str, str]:
        if not await database_probe() or not await model_probe():
            from notes_rag.api.errors import ApiError

            raise ApiError(503, "not_ready", "A aplicação ainda não está pronta.")
        return {"status": "ready"}

    app.include_router(router)
    web_dir = Path(__file__).parent / "web"
    app.mount("/static", StaticFiles(directory=web_dir, check_dir=True), name="static")

    @app.get("/", include_in_schema=False)
    async def index() -> FileResponse:
        return FileResponse(web_dir / "index.html")

    return app


app = create_app()
