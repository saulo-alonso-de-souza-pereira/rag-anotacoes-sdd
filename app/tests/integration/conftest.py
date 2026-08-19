import asyncio
import sys

import pytest
from testcontainers.postgres import PostgresContainer


@pytest.fixture(scope="session")
def event_loop_policy():
    if sys.platform == "win32":
        return asyncio.WindowsSelectorEventLoopPolicy()
    return asyncio.DefaultEventLoopPolicy()


@pytest.fixture(scope="session")
def postgres_url():
    with PostgresContainer("pgvector/pgvector:pg18", driver="psycopg") as postgres:
        yield postgres.get_connection_url()
