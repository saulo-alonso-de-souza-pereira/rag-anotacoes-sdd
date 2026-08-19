from uuid import UUID

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

RLS_SETTING = "app.current_user_id"


async def set_current_user(session: AsyncSession, user_id: UUID) -> None:
    await session.execute(
        text("SELECT set_config(:setting, :user_id, true)"),
        {"setting": RLS_SETTING, "user_id": str(user_id)},
    )


async def assert_current_user(session: AsyncSession, expected_user_id: UUID) -> None:
    actual = await session.scalar(
        text("SELECT current_setting(:setting, true)"), {"setting": RLS_SETTING}
    )
    if actual != str(expected_user_id):
        raise RuntimeError("rls_context_missing")
