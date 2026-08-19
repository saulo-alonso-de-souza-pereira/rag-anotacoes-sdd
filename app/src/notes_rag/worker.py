import asyncio
from collections.abc import Callable
from contextlib import suppress
from datetime import datetime

from sqlalchemy.ext.asyncio import async_sessionmaker

from notes_rag.config import get_settings
from notes_rag.llm.ollama import OllamaClient
from notes_rag.persistence.database import create_runtime_engine, create_session_factory
from notes_rag.persistence.repositories import IndexingRepository
from notes_rag.runtime import utc_now
from notes_rag.services.indexing import IndexingService


class IndexWorker:
    def __init__(
        self,
        sessions: async_sessionmaker,
        service_factory: Callable[[IndexingRepository], IndexingService],
        *,
        clock: Callable[[], datetime],
        poll_seconds: float,
        lease_seconds: int,
        use_claim_function: bool = False,
    ) -> None:
        self.sessions = sessions
        self.service_factory = service_factory
        self.clock = clock
        self.poll_seconds = poll_seconds
        self.lease_seconds = lease_seconds
        self.use_claim_function = use_claim_function
        self._stopping = asyncio.Event()

    async def run_once(self) -> bool:
        async with self.sessions() as session, session.begin():
            repository = IndexingRepository(session, use_claim_function=self.use_claim_function)
            job = await repository.claim_next(self.clock(), self.lease_seconds)
            if not job:
                return False
            return await self.service_factory(repository).process(job)

    async def run(self) -> None:
        while not self._stopping.is_set():
            processed = await self.run_once()
            if not processed:
                with suppress(TimeoutError):
                    await asyncio.wait_for(self._stopping.wait(), timeout=self.poll_seconds)

    def stop(self) -> None:
        self._stopping.set()


async def worker_main() -> None:
    settings = get_settings()
    engine = create_runtime_engine(settings)
    sessions = create_session_factory(engine)
    ollama = OllamaClient(
        str(settings.ollama_url),
        embedding_model=settings.embedding_model,
        generation_model=settings.generation_model,
    )
    worker = IndexWorker(
        sessions,
        lambda store: IndexingService(
            store,
            ollama,
            embedding_model=settings.embedding_model,
            clock=utc_now,
        ),
        clock=utc_now,
        poll_seconds=settings.worker_poll_seconds,
        lease_seconds=settings.worker_lease_seconds,
        use_claim_function=True,
    )
    try:
        await worker.run()
    finally:
        await ollama.close()
        await engine.dispose()


def main() -> None:
    asyncio.run(worker_main())


if __name__ == "__main__":
    main()
