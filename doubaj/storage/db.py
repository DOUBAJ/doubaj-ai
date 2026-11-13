"""Local SQLite storage for conversations, messages, projects, memory and settings."""
from __future__ import annotations

import json
import sqlite3
import threading
import time
from pathlib import Path
from typing import Any

SCHEMA = """
CREATE TABLE IF NOT EXISTS settings (
    key TEXT PRIMARY KEY,
    value TEXT
);
CREATE TABLE IF NOT EXISTS projects (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL,
    description TEXT DEFAULT '',
    instructions TEXT DEFAULT '',
    created_at REAL,
    updated_at REAL
);
CREATE TABLE IF NOT EXISTS project_files (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    project_id INTEGER REFERENCES projects(id) ON DELETE CASCADE,
    name TEXT,
    path TEXT,
    extracted_text TEXT,
    added_at REAL
);
CREATE TABLE IF NOT EXISTS conversations (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    title TEXT NOT NULL,
    project_id INTEGER REFERENCES projects(id) ON DELETE SET NULL,
    provider TEXT,
    model TEXT,
    created_at REAL,
    updated_at REAL
);
CREATE TABLE IF NOT EXISTS messages (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    conversation_id INTEGER REFERENCES conversations(id) ON DELETE CASCADE,
    role TEXT NOT NULL,
    content TEXT NOT NULL,
    attachments TEXT DEFAULT '[]',
    meta TEXT DEFAULT '{}',
    created_at REAL
);
CREATE TABLE IF NOT EXISTS memories (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    content TEXT NOT NULL,
    category TEXT DEFAULT 'general',
    project_id INTEGER REFERENCES projects(id) ON DELETE CASCADE,
    created_at REAL
);
CREATE TABLE IF NOT EXISTS outputs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    conversation_id INTEGER REFERENCES conversations(id) ON DELETE CASCADE,
    project_id INTEGER,
    name TEXT,
    path TEXT,
    kind TEXT,
    created_at REAL
);
CREATE INDEX IF NOT EXISTS idx_msg_conv ON messages(conversation_id);
"""


class Database:
    def __init__(self, path: Path):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._lock = threading.RLock()
        self.conn = sqlite3.connect(str(self.path), check_same_thread=False)
        self.conn.row_factory = sqlite3.Row
        self.conn.execute("PRAGMA foreign_keys = ON")
        self.conn.execute("PRAGMA journal_mode = WAL")
        self.conn.executescript(SCHEMA)
        self.conn.commit()

    # ---------- helpers ----------
    def _exec(self, sql: str, params: tuple = ()) -> sqlite3.Cursor:
        with self._lock:
            cur = self.conn.execute(sql, params)
            self.conn.commit()
            return cur

    def _all(self, sql: str, params: tuple = ()) -> list[dict]:
        with self._lock:
            return [dict(r) for r in self.conn.execute(sql, params).fetchall()]

    def _one(self, sql: str, params: tuple = ()) -> dict | None:
        with self._lock:
            r = self.conn.execute(sql, params).fetchone()
            return dict(r) if r else None

    # ---------- settings ----------
    def get_setting(self, key: str, default: Any = None) -> Any:
        row = self._one("SELECT value FROM settings WHERE key=?", (key,))
        if row is None:
            return default
        try:
            return json.loads(row["value"])
        except (TypeError, ValueError):
            return row["value"]

    def set_setting(self, key: str, value: Any) -> None:
        self._exec(
            "INSERT INTO settings(key,value) VALUES(?,?) "
            "ON CONFLICT(key) DO UPDATE SET value=excluded.value",
            (key, json.dumps(value, ensure_ascii=False)),
        )

    # ---------- conversations ----------
    def create_conversation(self, title: str, project_id: int | None = None,
                            provider: str = "", model: str = "") -> int:
        now = time.time()
        cur = self._exec(
            "INSERT INTO conversations(title,project_id,provider,model,created_at,updated_at)"
            " VALUES(?,?,?,?,?,?)", (title, project_id, provider, model, now, now))
        return cur.lastrowid

    def list_conversations(self, search: str = "", project_id: int | None = None) -> list[dict]:
        sql = "SELECT * FROM conversations"
        params: list = []
        where = []
        if project_id is not None:
            where.append("project_id=?")
            params.append(project_id)
        if search:
            where.append("(title LIKE ? OR id IN (SELECT conversation_id FROM messages WHERE content LIKE ?))")
            params += [f"%{search}%", f"%{search}%"]
        if where:
            sql += " WHERE " + " AND ".join(where)
        sql += " ORDER BY updated_at DESC"
        return self._all(sql, tuple(params))

    def get_conversation(self, conv_id: int) -> dict | None:
        return self._one("SELECT * FROM conversations WHERE id=?", (conv_id,))

    def rename_conversation(self, conv_id: int, title: str) -> None:
        self._exec("UPDATE conversations SET title=?, updated_at=? WHERE id=?", (title, time.time(), conv_id))

    def set_conversation_project(self, conv_id: int, project_id: int | None) -> None:
        self._exec("UPDATE conversations SET project_id=? WHERE id=?", (project_id, conv_id))

    def touch_conversation(self, conv_id: int, provider: str = "", model: str = "") -> None:
        self._exec("UPDATE conversations SET updated_at=?, provider=?, model=? WHERE id=?",
                   (time.time(), provider, model, conv_id))

    def delete_conversation(self, conv_id: int) -> None:
        self._exec("DELETE FROM conversations WHERE id=?", (conv_id,))

    def delete_all_conversations(self) -> None:
        self._exec("DELETE FROM conversations")

    # ---------- messages ----------
    def add_message(self, conv_id: int, role: str, content: str,
                    attachments: list | None = None, meta: dict | None = None) -> int:
        cur = self._exec(
            "INSERT INTO messages(conversation_id,role,content,attachments,meta,created_at) VALUES(?,?,?,?,?,?)",
            (conv_id, role, content, json.dumps(attachments or [], ensure_ascii=False),
             json.dumps(meta or {}, ensure_ascii=False), time.time()))
        return cur.lastrowid

    def update_message(self, msg_id: int, content: str, meta: dict | None = None) -> None:
        if meta is None:
            self._exec("UPDATE messages SET content=? WHERE id=?", (content, msg_id))
        else:
            self._exec("UPDATE messages SET content=?, meta=? WHERE id=?",
                       (content, json.dumps(meta, ensure_ascii=False), msg_id))

    def get_messages(self, conv_id: int) -> list[dict]:
        rows = self._all("SELECT * FROM messages WHERE conversation_id=? ORDER BY id", (conv_id,))
        for r in rows:
            r["attachments"] = json.loads(r["attachments"] or "[]")
            r["meta"] = json.loads(r["meta"] or "{}")
        return rows

    def delete_messages_from(self, conv_id: int, msg_id: int) -> None:
        """Delete message msg_id and everything after it (used by edit / regenerate)."""
        self._exec("DELETE FROM messages WHERE conversation_id=? AND id>=?", (conv_id, msg_id))

    # ---------- projects ----------
    def create_project(self, name: str, description: str = "", instructions: str = "") -> int:
        now = time.time()
        cur = self._exec("INSERT INTO projects(name,description,instructions,created_at,updated_at) VALUES(?,?,?,?,?)",
                         (name, description, instructions, now, now))
        return cur.lastrowid

    def update_project(self, pid: int, name: str, description: str, instructions: str) -> None:
        self._exec("UPDATE projects SET name=?,description=?,instructions=?,updated_at=? WHERE id=?",
                   (name, description, instructions, time.time(), pid))

    def list_projects(self) -> list[dict]:
        return self._all("SELECT * FROM projects ORDER BY updated_at DESC")

    def get_project(self, pid: int) -> dict | None:
        return self._one("SELECT * FROM projects WHERE id=?", (pid,))

    def delete_project(self, pid: int) -> None:
        self._exec("DELETE FROM projects WHERE id=?", (pid,))

    def add_project_file(self, pid: int, name: str, path: str, text: str) -> int:
        cur = self._exec("INSERT INTO project_files(project_id,name,path,extracted_text,added_at) VALUES(?,?,?,?,?)",
                         (pid, name, path, text, time.time()))
        return cur.lastrowid

    def list_project_files(self, pid: int) -> list[dict]:
        return self._all("SELECT * FROM project_files WHERE project_id=? ORDER BY id", (pid,))

    def delete_project_file(self, fid: int) -> None:
        self._exec("DELETE FROM project_files WHERE id=?", (fid,))

    # ---------- memory ----------
    def add_memory(self, content: str, category: str = "general", project_id: int | None = None) -> int:
        cur = self._exec("INSERT INTO memories(content,category,project_id,created_at) VALUES(?,?,?,?)",
                         (content, category, project_id, time.time()))
        return cur.lastrowid

    def list_memories(self, project_id: int | None = None, include_global: bool = True) -> list[dict]:
        if project_id is None:
            return self._all("SELECT * FROM memories ORDER BY id")
        if include_global:
            return self._all("SELECT * FROM memories WHERE project_id IS NULL OR project_id=? ORDER BY id", (project_id,))
        return self._all("SELECT * FROM memories WHERE project_id=? ORDER BY id", (project_id,))

    def update_memory(self, mid: int, content: str) -> None:
        self._exec("UPDATE memories SET content=? WHERE id=?", (content, mid))

    def delete_memory(self, mid: int) -> None:
        self._exec("DELETE FROM memories WHERE id=?", (mid,))

    def clear_memories(self) -> None:
        self._exec("DELETE FROM memories")

    # ---------- outputs ----------
    def add_output(self, conv_id: int | None, project_id: int | None, name: str, path: str, kind: str) -> int:
        cur = self._exec("INSERT INTO outputs(conversation_id,project_id,name,path,kind,created_at) VALUES(?,?,?,?,?,?)",
                         (conv_id, project_id, name, path, kind, time.time()))
        return cur.lastrowid

    def list_outputs(self, project_id: int | None = None) -> list[dict]:
        if project_id is None:
            return self._all("SELECT * FROM outputs ORDER BY id DESC")
        return self._all("SELECT * FROM outputs WHERE project_id=? ORDER BY id DESC", (project_id,))

    # ---------- export ----------
    def export_conversation(self, conv_id: int) -> dict:
        conv = self.get_conversation(conv_id) or {}
        return {"conversation": conv, "messages": self.get_messages(conv_id)}

    def backup_to(self, dest: Path) -> None:
        with self._lock:
            target = sqlite3.connect(str(dest))
            self.conn.backup(target)
            target.close()
