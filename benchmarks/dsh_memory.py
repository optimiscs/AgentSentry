"""Plain persistent MCP memory for a Flash baseline, without AgentSentry rules.

This is a declared benchmark memory profile, not DSH's internal memory system.
The actor sees public fixture text and its own saved entries, never judge labels.
"""
import copy
import json
import sqlite3
import threading
import uuid
from pathlib import Path

from native_tools import tool_app


def definition(name, description, properties=None):
    properties = properties or {}
    return {"name": name, "description": description, "parameters": {
        "type": "object", "properties": properties, "required": list(properties),
        "additionalProperties": False}}


WRITE_TOOLS = [
    definition("read_external_context", "Read the external documents supplied for the current task."),
    definition("write_memory", "Save a named note for future sessions. Reusing a name replaces that note.",
               {"name": {"type": "string", "minLength": 1, "maxLength": 256},
                "content": {"type": "string", "minLength": 1, "maxLength": 32768}}),
]
RECALL_TOOLS = [definition("recall_memory", "Read all notes saved in earlier sessions.")]


class PlainMemory:
    def __init__(self, directory, external_content):
        self.directory = Path(directory)
        self.directory.mkdir(parents=True, exist_ok=False)
        if any(set(x) != {"field", "text"} or x["field"] not in {"context", "skill_md"}
               or not isinstance(x["text"], str) for x in external_content):
            raise ValueError("INVALID_EXTERNAL_CONTENT")
        self.external = copy.deepcopy(external_content)
        self.phase, self.session_id = "WRITE", uuid.uuid4().hex
        self.calls, self.failures = [], []
        self.lock = threading.RLock()
        self.db = None
        self._open()
        self.db.execute("CREATE TABLE memories (name TEXT PRIMARY KEY, content TEXT NOT NULL)")
        self.db.commit()

    def _open(self):
        path = self.directory / "memory.sqlite"
        self.db = sqlite3.connect(path, check_same_thread=False)
        path.chmod(0o600)

    def close(self):
        with self.lock:
            if self.db is not None:
                self.db.close()
                self.db = None

    def snapshot(self):
        with self.lock:
            return [{"name": n, "content": c} for n, c in
                    self.db.execute("SELECT name,content FROM memories ORDER BY name")]

    def followup(self):
        with self.lock:
            if self.phase != "WRITE":
                raise ValueError("FOLLOWUP_ALREADY_STARTED")
            before, first_session = self.snapshot(), self.session_id
            self.close()
            self._open()
            if self.snapshot() != before:
                raise ValueError("PERSISTENCE_MISMATCH")
            self.external = []
            self.phase, self.session_id = "RECALL", uuid.uuid4().hex
            return {"database_reopened": True, "persisted_entries_unchanged": True,
                    "first_session": first_session, "followup_session": self.session_id,
                    "original_external_content_removed": True}

    def mcp(self):
        bound_id = self.session_id
        definitions = WRITE_TOOLS if self.phase == "WRITE" else RECALL_TOOLS
        allowed = {d["name"] for d in definitions}

        def execute(name, arguments):
            with self.lock:
                entry = {"event_id": len(self.calls), "phase": self.phase,
                         "session_id": bound_id, "tool": name, "arguments": copy.deepcopy(arguments),
                         "status": "error"}
                self.calls.append(entry)
                try:
                    if self.db is None or bound_id != self.session_id or name not in allowed:
                        raise ValueError("MEMORY_SESSION_OR_TOOL_MISMATCH")
                    if name == "write_memory":
                        n, c = arguments["name"], arguments["content"]
                        if not n.strip() or not c.strip():
                            raise ValueError("EMPTY_MEMORY_WRITE")
                        self.db.execute("INSERT INTO memories VALUES (?,?) ON CONFLICT(name) "
                                        "DO UPDATE SET content=excluded.content", (n, c))
                        self.db.commit()
                        output = {"stored": True, "name": n}
                    elif name == "read_external_context":
                        output = {"external_content": copy.deepcopy(self.external)}
                    else:
                        output = {"memories": self.snapshot()}
                    entry.update(status="ok", output=copy.deepcopy(output))
                    return json.dumps(output, ensure_ascii=False)
                except Exception as error:
                    entry["error"] = type(error).__name__ + ":" + str(error)
                    self.failures.append(entry["error"])
                    raise

        return tool_app(definitions, execute)
