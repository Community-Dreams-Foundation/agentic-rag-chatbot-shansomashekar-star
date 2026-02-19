import aiosqlite
import os
from typing import Any, List, Optional

from app.config import settings


async def get_db() -> aiosqlite.Connection:
    os.makedirs(os.path.dirname(settings.db_path) or ".", exist_ok=True)
    conn = await aiosqlite.connect(settings.db_path)
    conn.row_factory = aiosqlite.Row
    return conn


async def init_schema(conn: aiosqlite.Connection) -> None:
    await conn.executescript("""
        CREATE TABLE IF NOT EXISTS users (
            id TEXT PRIMARY KEY,
            username TEXT UNIQUE NOT NULL,
            password_hash TEXT NOT NULL,
            created_at INTEGER NOT NULL
        );

        CREATE TABLE IF NOT EXISTS documents (
            id TEXT PRIMARY KEY,
            user_id TEXT NOT NULL,
            filename TEXT NOT NULL,
            summary TEXT,
            created_at INTEGER NOT NULL,
            FOREIGN KEY (user_id) REFERENCES users(id)
        );

        CREATE TABLE IF NOT EXISTS chunks (
            id TEXT PRIMARY KEY,
            doc_id TEXT NOT NULL,
            user_id TEXT NOT NULL,
            parent_idx INTEGER NOT NULL,
            child_idx INTEGER NOT NULL,
            parent_text TEXT NOT NULL,
            child_text TEXT NOT NULL,
            source TEXT NOT NULL,
            page INTEGER,
            section TEXT,
            created_at INTEGER NOT NULL,
            FOREIGN KEY (doc_id) REFERENCES documents(id),
            FOREIGN KEY (user_id) REFERENCES users(id)
        );

        CREATE INDEX IF NOT EXISTS idx_chunks_user ON chunks(user_id);
        CREATE INDEX IF NOT EXISTS idx_chunks_doc ON chunks(doc_id);
        CREATE INDEX IF NOT EXISTS idx_chunks_parent ON chunks(user_id, doc_id, parent_idx);
    """)


async def create_user(conn: aiosqlite.Connection, user_id: str, username: str, password_hash: str) -> None:
    import time
    await conn.execute(
        "INSERT INTO users (id, username, password_hash, created_at) VALUES (?, ?, ?, ?)",
        (user_id, username, password_hash, int(time.time())),
    )
    await conn.commit()


async def get_user_by_username(conn: aiosqlite.Connection, username: str) -> Optional[dict]:
    cursor = await conn.execute(
        "SELECT id, username, password_hash FROM users WHERE username = ?",
        (username,),
    )
    row = await cursor.fetchone()
    return dict(row) if row else None


async def get_user_by_id(conn: aiosqlite.Connection, user_id: str) -> Optional[dict]:
    cursor = await conn.execute(
        "SELECT id, username FROM users WHERE id = ?",
        (user_id,),
    )
    row = await cursor.fetchone()
    return dict(row) if row else None


async def insert_document(conn: aiosqlite.Connection, doc_id: str, user_id: str, filename: str, summary: str = "") -> None:
    import time
    await conn.execute(
        "INSERT INTO documents (id, user_id, filename, summary, created_at) VALUES (?, ?, ?, ?, ?)",
        (doc_id, user_id, filename, summary, int(time.time())),
    )
    await conn.commit()


async def insert_chunks(conn: aiosqlite.Connection, chunks: List[dict]) -> None:
    import time
    now = int(time.time())
    for c in chunks:
        await conn.execute(
            """INSERT INTO chunks (id, doc_id, user_id, parent_idx, child_idx, parent_text, child_text, source, page, section, created_at)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                c["id"],
                c["doc_id"],
                c["user_id"],
                c["parent_idx"],
                c["child_idx"],
                c["parent_text"],
                c["child_text"],
                c["source"],
                c.get("page"),
                c.get("section"),
                now,
            ),
        )
    await conn.commit()


async def get_parent_texts(conn: aiosqlite.Connection, user_id: str, parent_keys: List[tuple]) -> List[str]:
    results = []
    for doc_id, parent_idx in parent_keys:
        cursor = await conn.execute(
            "SELECT parent_text FROM chunks WHERE user_id = ? AND doc_id = ? AND parent_idx = ? LIMIT 1",
            (user_id, doc_id, parent_idx),
        )
        row = await cursor.fetchone()
        if row:
            results.append(row["parent_text"])
    return results


async def get_documents_for_user(conn: aiosqlite.Connection, user_id: str) -> List[dict]:
    cursor = await conn.execute(
        "SELECT id, filename, summary, created_at FROM documents WHERE user_id = ? ORDER BY created_at DESC",
        (user_id,),
    )
    rows = await cursor.fetchall()
    return [dict(r) for r in rows]


async def delete_document_chunks(conn: aiosqlite.Connection, user_id: str, doc_id: str) -> int:
    cursor = await conn.execute("DELETE FROM chunks WHERE user_id = ? AND doc_id = ?", (user_id, doc_id))
    await conn.execute("DELETE FROM documents WHERE id = ? AND user_id = ?", (doc_id, user_id))
    await conn.commit()
    return cursor.rowcount


async def get_chunk_count_for_user(conn: aiosqlite.Connection, user_id: str) -> int:
    cursor = await conn.execute("SELECT COUNT(*) as n FROM chunks WHERE user_id = ?", (user_id,))
    row = await cursor.fetchone()
    return row["n"] if row else 0
