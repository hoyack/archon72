"""Helpers for executing SQL migration files in tests."""

from __future__ import annotations

from pathlib import Path

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession


def _split_sql_statements(sql: str) -> list[str]:
    """Split SQL into statements, respecting dollar-quoted blocks."""
    statements: list[str] = []
    buffer: list[str] = []
    in_dollar = False
    dollar_tag = ""
    i = 0
    length = len(sql)

    while i < length:
        ch = sql[i]
        if ch == "$":
            # Detect dollar-quote tag ($$ or $tag$)
            j = i + 1
            while j < length and (sql[j].isalnum() or sql[j] == "_"):
                j += 1
            if j < length and sql[j] == "$":
                tag = sql[i : j + 1]
                if not in_dollar:
                    in_dollar = True
                    dollar_tag = tag
                elif tag == dollar_tag:
                    in_dollar = False
                    dollar_tag = ""
                buffer.append(tag)
                i = j + 1
                continue
        if ch == ";" and not in_dollar:
            statements.append("".join(buffer))
            buffer = []
            i += 1
            continue
        buffer.append(ch)
        i += 1

    if buffer:
        statements.append("".join(buffer))
    return statements


def _has_sql(statement: str) -> bool:
    for line in statement.splitlines():
        stripped = line.strip()
        if stripped and not stripped.startswith("--"):
            return True
    return False


async def execute_sql_file(db_session: AsyncSession, path: Path) -> None:
    """Execute a SQL file, skipping comment-only chunks."""
    sql = path.read_text()
    for statement in _split_sql_statements(sql):
        if _has_sql(statement):
            await db_session.execute(text(statement))
