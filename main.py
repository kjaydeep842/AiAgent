#!/usr/bin/env python3
import json
import os
import shlex
import sqlite3
import subprocess
import uuid
from contextlib import closing
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from openai import APIError, AuthenticationError, BadRequestError, OpenAI, PermissionDeniedError, RateLimitError
from pydantic import BaseModel, Field
try:
    from dotenv import load_dotenv
except ImportError:  # pragma: no cover
    def load_dotenv(*_args: Any, **_kwargs: Any) -> bool:
        return False


APP_DIR = Path(__file__).resolve().parent
STATIC_DIR = APP_DIR / "static"
DATA_DIR = APP_DIR / "data"
DB_PATH = DATA_DIR / "agent.db"
WORKSPACE_ROOT = APP_DIR
load_dotenv(APP_DIR / ".env")
OPENROUTER_BASE_URL = "https://openrouter.ai/api/v1"
MAX_FILE_BYTES = 64_000
MAX_COMMAND_OUTPUT = 12_000
MAX_TOOL_ROUNDS = 8
ENABLE_LOCAL_FALLBACK = os.getenv("ENABLE_LOCAL_FALLBACK", "1") == "1"


SYSTEM_PROMPT = """You are Atlas, a capable general-purpose AI workspace agent.

You help with:
- coding and debugging
- writing and rewriting
- project planning
- documentation
- file inspection and editing
- shell-based diagnostics
- lightweight persistent memory

Behavior:
- Be concise, useful, and action-oriented.
- Prefer using tools instead of guessing.
- Explain briefly before edits or commands.
- Stay inside the allowed workspace.
- If a tool fails, adapt and continue when possible.
"""


class ChatRequest(BaseModel):
    session_id: str | None = None
    message: str = Field(min_length=1)
    model: str | None = None
    workspace: str | None = None


class SessionCreateRequest(BaseModel):
    title: str = "New Session"


class MemoryRequest(BaseModel):
    text: str = Field(min_length=1)


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def get_provider() -> str:
    configured = os.getenv("AI_PROVIDER")
    if configured:
        return configured.lower()
    if os.getenv("OPENROUTER_API_KEY"):
        return "openrouter"
    if os.getenv("OPENAI_API_KEY"):
        return "openai"
    return "openrouter"


def get_default_model() -> str:
    if get_provider() == "openrouter":
        return os.getenv("AI_MODEL") or "openrouter/free"
    return os.getenv("AI_MODEL") or os.getenv("OPENAI_MODEL") or "gpt-5.4-mini"


def get_api_key_name() -> str:
    return "OPENROUTER_API_KEY" if get_provider() == "openrouter" else "OPENAI_API_KEY"


def get_api_key() -> str | None:
    if get_provider() == "openrouter":
        return os.getenv("OPENROUTER_API_KEY") or os.getenv("AI_API_KEY")
    return os.getenv("OPENAI_API_KEY") or os.getenv("AI_API_KEY")


def get_base_url() -> str | None:
    if os.getenv("AI_BASE_URL"):
        return os.getenv("AI_BASE_URL")
    if get_provider() == "openrouter":
        return OPENROUTER_BASE_URL
    return None


def get_client() -> OpenAI:
    api_key = get_api_key()
    if not api_key:
        raise HTTPException(status_code=400, detail=f"Missing {get_api_key_name()} environment variable.")

    default_headers: dict[str, str] = {}
    if get_provider() == "openrouter":
        default_headers["HTTP-Referer"] = os.getenv("OPENROUTER_SITE_URL", "http://127.0.0.1:8000")
        default_headers["X-Title"] = os.getenv("OPENROUTER_APP_NAME", "Atlas Agent")

    return OpenAI(
        api_key=api_key,
        base_url=get_base_url(),
        default_headers=default_headers or None,
    )


def build_laravel_role_reply(user_message: str) -> str:
    return """Local fallback mode is active, so I am giving you a strong starter implementation instead of a hosted-model response.

For a Laravel role management setup, the simplest clean approach is to use 3 tables: `roles`, `permissions`, and `role_user`.

Example migration for `roles`:

```php
Schema::create('roles', function (Blueprint $table) {
    $table->id();
    $table->string('name')->unique();
    $table->string('slug')->unique();
    $table->timestamps();
});
```

Example migration for `role_user`:

```php
Schema::create('role_user', function (Blueprint $table) {
    $table->id();
    $table->foreignId('user_id')->constrained()->cascadeOnDelete();
    $table->foreignId('role_id')->constrained()->cascadeOnDelete();
    $table->timestamps();
});
```

Example `Role` model:

```php
class Role extends Model
{
    protected $fillable = ['name', 'slug'];

    public function users()
    {
        return $this->belongsToMany(User::class);
    }
}
```

Example additions in `User` model:

```php
public function roles()
{
    return $this->belongsToMany(Role::class);
}

public function hasRole(string $role): bool
{
    return $this->roles()->where('slug', $role)->exists();
}
```

Example middleware check:

```php
if (!auth()->user() || !auth()->user()->hasRole('admin')) {
    abort(403, 'Unauthorized');
}
```

Next recommended steps:
1. Create `RoleController` CRUD for add/edit/delete roles.
2. Add role assignment UI in user management.
3. Add middleware like `role:admin`.
4. Seed default roles such as `admin`, `manager`, and `staff`.

If you want, ask again with:
`Create full Laravel role management code with migration, model, middleware, controller, routes, and blade files`

    and I can continue in local fallback mode with a fuller scaffold.
    """


def build_react_dashboard_reply() -> str:
    return """Local fallback mode is active, so here is a working React dashboard starter component.

```jsx
import "./dashboard.css";

const stats = [
  { label: "Revenue", value: "$24,500", change: "+12%" },
  { label: "Users", value: "1,248", change: "+8%" },
  { label: "Orders", value: "320", change: "+5%" },
  { label: "Errors", value: "7", change: "-2%" },
];

const activities = [
  "New user registered",
  "Payment received from Acme Ltd",
  "Server backup completed",
  "Manager updated sales report",
];

export default function Dashboard() {
  return (
    <main className="dashboard">
      <header className="dashboard-header">
        <div>
          <p className="eyebrow">Overview</p>
          <h1>Business Dashboard</h1>
        </div>
        <button className="primary-btn">Export Report</button>
      </header>

      <section className="stats-grid">
        {stats.map((item) => (
          <article className="card stat-card" key={item.label}>
            <span>{item.label}</span>
            <h2>{item.value}</h2>
            <small>{item.change} this month</small>
          </article>
        ))}
      </section>

      <section className="content-grid">
        <article className="card chart-card">
          <h3>Sales Performance</h3>
          <div className="chart-placeholder">
            <div style={{ height: "45%" }} />
            <div style={{ height: "70%" }} />
            <div style={{ height: "55%" }} />
            <div style={{ height: "88%" }} />
            <div style={{ height: "62%" }} />
            <div style={{ height: "92%" }} />
          </div>
        </article>

        <article className="card activity-card">
          <h3>Recent Activity</h3>
          <ul>
            {activities.map((item) => (
              <li key={item}>{item}</li>
            ))}
          </ul>
        </article>
      </section>
    </main>
  );
}
```

```css
.dashboard {
  padding: 24px;
  background: #f7f5ef;
  min-height: 100vh;
  font-family: Arial, sans-serif;
}

.dashboard-header,
.stats-grid,
.content-grid {
  display: grid;
  gap: 16px;
}

.dashboard-header {
  grid-template-columns: 1fr auto;
  align-items: center;
  margin-bottom: 24px;
}

.eyebrow {
  color: #777;
  margin: 0 0 8px;
  text-transform: uppercase;
  font-size: 12px;
}

.stats-grid {
  grid-template-columns: repeat(auto-fit, minmax(180px, 1fr));
  margin-bottom: 24px;
}

.content-grid {
  grid-template-columns: 2fr 1fr;
}

.card {
  background: white;
  border-radius: 18px;
  padding: 20px;
  box-shadow: 0 10px 30px rgba(0, 0, 0, 0.06);
}

.stat-card h2 {
  margin: 12px 0 8px;
}

.chart-placeholder {
  display: flex;
  align-items: end;
  gap: 12px;
  height: 240px;
  margin-top: 20px;
}

.chart-placeholder div {
  flex: 1;
  background: linear-gradient(180deg, #0f766e, #6ee7b7);
  border-radius: 12px 12px 0 0;
}

.activity-card ul {
  padding-left: 18px;
  line-height: 1.8;
}

.primary-btn {
  border: 0;
  background: #0f766e;
  color: white;
  padding: 12px 18px;
  border-radius: 12px;
  cursor: pointer;
}

@media (max-width: 900px) {
  .content-grid,
  .dashboard-header {
    grid-template-columns: 1fr;
  }
}
```

If you want, I can also generate:
1. `Dashboard.jsx` and `dashboard.css` as separate files
2. a Tailwind version
3. a React admin panel with sidebar, charts, and tables
"""


def build_generic_code_reply(user_message: str) -> str:
    return f"""Local fallback mode is active, and I can still give you code directly.

Starter code response for:
`{user_message}`

```js
export function starterFeature() {{
  return {{
    ok: true,
    message: "Replace this starter with your exact business logic.",
  }};
}}
```

To get a much better code response, ask with one of these exact styles:
1. `Create full Laravel CRUD for roles with controller, model, migration, routes, and blade files`
2. `Build React dashboard page with cards, chart section, sidebar, and responsive CSS`
3. `Create Node.js Express login API with JWT and MySQL`
4. `Write PHP controller to store product data with validation`

If you want, send one exact feature request now and I will return full code in local mode.
"""


def build_general_reply(user_message: str) -> str:
    return f"""Local fallback mode is active, so I am answering without a hosted AI provider.

Here is a practical response to your request:
`{user_message}`

I can still help best with:
1. coding and file generation
2. debugging and fixing logic
3. Laravel, React, Node.js, PHP, and API scaffolds
4. project planning and implementation steps

If you want a stronger answer, ask with clear intent such as:
- `Explain this bug in my Laravel controller`
- `Create full React dashboard code`
- `Write authentication API in Node.js`
- `Plan database schema for ecommerce app`
"""


def build_local_reply(user_message: str) -> str:
    prompt = user_message.lower()
    if "laravel" in prompt and "role" in prompt:
        return build_laravel_role_reply(user_message)
    if "react" in prompt and "dashboard" in prompt:
        return build_react_dashboard_reply()
    if any(word in prompt for word in ["code", "build", "create", "api", "app", "controller", "model"]):
        return build_generic_code_reply(user_message)
    return build_general_reply(user_message)


def init_db() -> None:
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    with sqlite3.connect(DB_PATH) as conn:
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS sessions (
                id TEXT PRIMARY KEY,
                title TEXT NOT NULL,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL
            )
            """
        )
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS messages (
                id TEXT PRIMARY KEY,
                session_id TEXT NOT NULL,
                role TEXT NOT NULL,
                content TEXT NOT NULL,
                created_at TEXT NOT NULL,
                FOREIGN KEY(session_id) REFERENCES sessions(id)
            )
            """
        )
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS memories (
                id TEXT PRIMARY KEY,
                text TEXT NOT NULL,
                created_at TEXT NOT NULL
            )
            """
        )
        conn.commit()


def db_all(query: str, params: tuple[Any, ...] = ()) -> list[dict[str, Any]]:
    with closing(sqlite3.connect(DB_PATH)) as conn:
        conn.row_factory = sqlite3.Row
        rows = conn.execute(query, params).fetchall()
    return [dict(row) for row in rows]


def db_one(query: str, params: tuple[Any, ...] = ()) -> dict[str, Any] | None:
    rows = db_all(query, params)
    return rows[0] if rows else None


def db_run(query: str, params: tuple[Any, ...] = ()) -> None:
    with sqlite3.connect(DB_PATH) as conn:
        conn.execute(query, params)
        conn.commit()


def delete_session(session_id: str) -> None:
    get_session(session_id)
    db_run("DELETE FROM messages WHERE session_id = ?", (session_id,))
    db_run("DELETE FROM sessions WHERE id = ?", (session_id,))


def ensure_workspace(path_str: str | None) -> Path:
    base = WORKSPACE_ROOT.resolve()
    target = (Path(path_str).resolve() if path_str else base)
    try:
        target.relative_to(base)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail="Workspace must stay inside the project directory.") from exc
    target.mkdir(parents=True, exist_ok=True)
    return target


def ensure_target(workspace: Path, relative_path: str) -> Path:
    target = (workspace / relative_path).resolve()
    try:
        target.relative_to(workspace.resolve())
    except ValueError as exc:
        raise ValueError(f"Path must stay inside workspace: {relative_path}") from exc
    return target


def infer_title(message: str) -> str:
    compact = " ".join(message.strip().split())
    return compact[:48] or "New Session"


def create_session(title: str) -> dict[str, Any]:
    session_id = str(uuid.uuid4())
    now = utc_now()
    db_run(
        "INSERT INTO sessions (id, title, created_at, updated_at) VALUES (?, ?, ?, ?)",
        (session_id, title, now, now),
    )
    return get_session(session_id)


def get_session(session_id: str) -> dict[str, Any]:
    session = db_one("SELECT * FROM sessions WHERE id = ?", (session_id,))
    if not session:
        raise HTTPException(status_code=404, detail="Session not found.")
    return session


def add_message(session_id: str, role: str, content: str) -> dict[str, Any]:
    message = {
        "id": str(uuid.uuid4()),
        "session_id": session_id,
        "role": role,
        "content": content,
        "created_at": utc_now(),
    }
    db_run(
        "INSERT INTO messages (id, session_id, role, content, created_at) VALUES (?, ?, ?, ?, ?)",
        (message["id"], session_id, role, content, message["created_at"]),
    )
    db_run("UPDATE sessions SET updated_at = ? WHERE id = ?", (utc_now(), session_id))
    return message


def get_session_messages(session_id: str) -> list[dict[str, Any]]:
    return db_all(
        "SELECT id, session_id, role, content, created_at FROM messages WHERE session_id = ? ORDER BY created_at ASC",
        (session_id,),
    )


def build_prompt_messages(session_id: str, workspace: Path) -> list[dict[str, Any]]:
    memories = db_all("SELECT text, created_at FROM memories ORDER BY created_at DESC LIMIT 10")
    memory_text = "\n".join(f"- {row['text']} ({row['created_at']})" for row in memories) or "- No saved memory yet."

    messages: list[dict[str, Any]] = [
        {
            "role": "system",
            "content": (
                f"{SYSTEM_PROMPT}\n\n"
                f"Workspace root: {workspace}\n"
                f"Saved memory:\n{memory_text}"
            ),
        }
    ]

    for row in get_session_messages(session_id):
        messages.append({"role": row["role"], "content": row["content"]})
    return messages


def list_files(workspace: Path, relative_dir: str = ".") -> str:
    target = ensure_target(workspace, relative_dir)
    if not target.exists():
        return json.dumps({"error": f"Directory not found: {relative_dir}"})
    if not target.is_dir():
        return json.dumps({"error": f"Not a directory: {relative_dir}"})
    entries = []
    for child in sorted(target.iterdir(), key=lambda item: (item.is_file(), item.name.lower())):
        entries.append(
            {
                "name": child.name,
                "type": "dir" if child.is_dir() else "file",
                "path": str(child.relative_to(workspace)),
            }
        )
    return json.dumps({"directory": str(target.relative_to(workspace)), "entries": entries}, indent=2)


def read_file(workspace: Path, relative_path: str) -> str:
    target = ensure_target(workspace, relative_path)
    if not target.exists():
        return json.dumps({"error": f"File not found: {relative_path}"})
    if not target.is_file():
        return json.dumps({"error": f"Not a file: {relative_path}"})
    size = target.stat().st_size
    if size > MAX_FILE_BYTES:
        return json.dumps({"error": f"File too large to read directly ({size} bytes).", "max_bytes": MAX_FILE_BYTES})
    return target.read_text(encoding="utf-8", errors="replace")


def write_file(workspace: Path, relative_path: str, content: str, mode: str) -> str:
    target = ensure_target(workspace, relative_path)
    target.parent.mkdir(parents=True, exist_ok=True)
    if mode == "append":
        with target.open("a", encoding="utf-8") as handle:
            handle.write(content)
    else:
        target.write_text(content, encoding="utf-8")
    return json.dumps({"status": "ok", "path": str(target.relative_to(workspace)), "mode": mode})


def search_workspace(workspace: Path, pattern: str) -> str:
    matches = []
    query = pattern.lower()
    for path in workspace.rglob("*"):
        if not path.is_file():
            continue
        relative = str(path.relative_to(workspace))
        if query in relative.lower():
            matches.append({"path": relative, "match_type": "path"})
            if len(matches) >= 50:
                break
            continue
        try:
            text = path.read_text(encoding="utf-8", errors="ignore")
        except OSError:
            continue
        if query in text.lower():
            matches.append({"path": relative, "match_type": "content"})
            if len(matches) >= 50:
                break
    return json.dumps({"pattern": pattern, "matches": matches}, indent=2)


def run_command(workspace: Path, command: str) -> str:
    blocked = {"rm", "sudo", "shutdown", "reboot", "mkfs", "dd", "chmod", "chown"}
    parts = shlex.split(command)
    if not parts:
        return json.dumps({"error": "Empty command"})
    if parts[0] in blocked:
        return json.dumps({"error": f"Blocked command: {parts[0]}"})
    result = subprocess.run(
        command,
        cwd=workspace,
        shell=True,
        capture_output=True,
        text=True,
        timeout=30,
    )
    output = ((result.stdout or "") + (result.stderr or ""))[:MAX_COMMAND_OUTPUT]
    return json.dumps(
        {
            "command": command,
            "exit_code": result.returncode,
            "output": output,
            "truncated": len(output) >= MAX_COMMAND_OUTPUT,
        },
        indent=2,
    )


def save_memory(text: str) -> str:
    memory = {"id": str(uuid.uuid4()), "text": text, "created_at": utc_now()}
    db_run("INSERT INTO memories (id, text, created_at) VALUES (?, ?, ?)", (memory["id"], memory["text"], memory["created_at"]))
    return json.dumps({"status": "saved", "memory": memory}, indent=2)


def get_memory() -> str:
    memories = db_all("SELECT id, text, created_at FROM memories ORDER BY created_at DESC LIMIT 50")
    return json.dumps({"items": memories}, indent=2)


def get_time() -> str:
    now = datetime.now().astimezone()
    return json.dumps({"local_time": now.isoformat(), "utc_time": utc_now()}, indent=2)


TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "list_files",
            "description": "List files and folders in a workspace directory.",
            "parameters": {
                "type": "object",
                "properties": {
                    "relative_dir": {"type": "string", "description": "Directory relative to workspace root."}
                },
                "required": ["relative_dir"],
                "additionalProperties": False,
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "read_file",
            "description": "Read a text file from the workspace.",
            "parameters": {
                "type": "object",
                "properties": {
                    "relative_path": {"type": "string", "description": "File path relative to workspace root."}
                },
                "required": ["relative_path"],
                "additionalProperties": False,
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "write_file",
            "description": "Create or update a file in the workspace.",
            "parameters": {
                "type": "object",
                "properties": {
                    "relative_path": {"type": "string"},
                    "content": {"type": "string"},
                    "mode": {"type": "string", "enum": ["overwrite", "append"]},
                },
                "required": ["relative_path", "content", "mode"],
                "additionalProperties": False,
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "search_workspace",
            "description": "Search workspace file paths and contents.",
            "parameters": {
                "type": "object",
                "properties": {"pattern": {"type": "string"}},
                "required": ["pattern"],
                "additionalProperties": False,
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "run_command",
            "description": "Run a non-destructive shell command in the workspace.",
            "parameters": {
                "type": "object",
                "properties": {"command": {"type": "string"}},
                "required": ["command"],
                "additionalProperties": False,
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "save_memory",
            "description": "Save a memory note for future sessions.",
            "parameters": {
                "type": "object",
                "properties": {"text": {"type": "string"}},
                "required": ["text"],
                "additionalProperties": False,
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_memory",
            "description": "Return saved memory notes.",
            "parameters": {"type": "object", "properties": {}, "additionalProperties": False},
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_time",
            "description": "Return local and UTC time.",
            "parameters": {"type": "object", "properties": {}, "additionalProperties": False},
        },
    },
]


def execute_tool(workspace: Path, name: str, args: dict[str, Any]) -> str:
    try:
        if name == "list_files":
            return list_files(workspace, args.get("relative_dir", "."))
        if name == "read_file":
            return read_file(workspace, args["relative_path"])
        if name == "write_file":
            return write_file(workspace, args["relative_path"], args["content"], args["mode"])
        if name == "search_workspace":
            return search_workspace(workspace, args["pattern"])
        if name == "run_command":
            return run_command(workspace, args["command"])
        if name == "save_memory":
            return save_memory(args["text"])
        if name == "get_memory":
            return get_memory()
        if name == "get_time":
            return get_time()
    except Exception as exc:  # noqa: BLE001
        return json.dumps({"error": str(exc)})
    return json.dumps({"error": f"Unknown tool: {name}"})


def run_agent(session_id: str, user_message: str, model: str, workspace: Path) -> dict[str, Any]:
    if model == "local-demo":
        return {"reply": build_local_reply(user_message), "tool_events": []}

    try:
        client = get_client()
    except HTTPException:
        if ENABLE_LOCAL_FALLBACK:
            return {"reply": build_local_reply(user_message), "tool_events": []}
        raise

    chat_messages = build_prompt_messages(session_id, workspace)
    chat_messages.append({"role": "user", "content": user_message})
    tool_events: list[dict[str, Any]] = []

    for _ in range(MAX_TOOL_ROUNDS):
        try:
            response = client.chat.completions.create(
                model=model,
                messages=chat_messages,
                tools=TOOLS,
                tool_choice="auto",
            )
        except BadRequestError as exc:
            error_message = "OpenAI request failed."
            try:
                payload = json.loads(exc.response.text)
                error_message = payload.get("error", {}).get("message", error_message)
            except Exception:  # noqa: BLE001
                error_message = str(exc)
            return {"reply": f"Agent request error: {error_message}", "tool_events": tool_events}
        except AuthenticationError:
            if ENABLE_LOCAL_FALLBACK:
                return {"reply": build_local_reply(user_message), "tool_events": tool_events}
            return {
                "reply": "Agent configuration error: the OpenAI API key is invalid or rejected. Update the key in .env and restart the server.",
                "tool_events": tool_events,
            }
        except PermissionDeniedError:
            if ENABLE_LOCAL_FALLBACK:
                return {"reply": build_local_reply(user_message), "tool_events": tool_events}
            return {
                "reply": "Agent permission error: this API key does not have access to the selected model or feature.",
                "tool_events": tool_events,
            }
        except RateLimitError as exc:
            if ENABLE_LOCAL_FALLBACK:
                return {"reply": build_local_reply(user_message), "tool_events": tool_events}
            error_message = "Rate limit or quota issue."
            try:
                payload = json.loads(exc.response.text)
                error_message = payload.get("error", {}).get("message", error_message)
            except Exception:  # noqa: BLE001
                error_message = str(exc)
            return {
                "reply": f"Agent billing issue: {error_message}",
                "tool_events": tool_events,
            }
        except APIError as exc:
            return {
                "reply": f"Agent API error: {exc}",
                "tool_events": tool_events,
            }
        except Exception as exc:  # noqa: BLE001
            return {
                "reply": f"Agent internal error: {exc}",
                "tool_events": tool_events,
            }

        message = response.choices[0].message
        tool_calls = getattr(message, "tool_calls", None) or []

        if not tool_calls:
            return {"reply": message.content or "No response returned.", "tool_events": tool_events}

        chat_messages.append(
            {
                "role": "assistant",
                "content": message.content or "",
                "tool_calls": [
                    {
                        "id": tool_call.id,
                        "type": "function",
                        "function": {
                            "name": tool_call.function.name,
                            "arguments": tool_call.function.arguments,
                        },
                    }
                    for tool_call in tool_calls
                ],
            }
        )

        for tool_call in tool_calls:
            args = json.loads(tool_call.function.arguments or "{}")
            result = execute_tool(workspace, tool_call.function.name, args)
            tool_events.append({"name": tool_call.function.name, "arguments": args, "result": result})
            chat_messages.append(
                {
                    "role": "tool",
                    "tool_call_id": tool_call.id,
                    "content": result,
                }
            )

    return {
        "reply": "I reached the tool-round limit while working on that request. Please narrow the task and try again.",
        "tool_events": tool_events,
    }


app = FastAPI(title="Atlas Agent")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")


@app.on_event("startup")
def on_startup() -> None:
    init_db()


@app.get("/")
def serve_index() -> FileResponse:
    return FileResponse(STATIC_DIR / "index.html")


@app.get("/api/health")
def health() -> dict[str, Any]:
    return {
        "ok": True,
        "provider": get_provider(),
        "default_model": get_default_model(),
        "workspace_root": str(WORKSPACE_ROOT),
        "api_key_configured": bool(get_api_key()),
        "api_key_name": get_api_key_name(),
        "local_fallback_enabled": ENABLE_LOCAL_FALLBACK,
    }


@app.get("/api/sessions")
def list_sessions() -> list[dict[str, Any]]:
    return db_all("SELECT * FROM sessions ORDER BY updated_at DESC")


@app.post("/api/sessions")
def create_session_endpoint(payload: SessionCreateRequest) -> dict[str, Any]:
    return create_session(payload.title)


@app.get("/api/sessions/{session_id}")
def get_session_endpoint(session_id: str) -> dict[str, Any]:
    session = get_session(session_id)
    return {"session": session, "messages": get_session_messages(session_id)}


@app.delete("/api/sessions/{session_id}")
def delete_session_endpoint(session_id: str) -> dict[str, Any]:
    delete_session(session_id)
    return {"status": "deleted", "session_id": session_id}


@app.post("/api/chat")
def chat(payload: ChatRequest) -> dict[str, Any]:
    workspace = ensure_workspace(payload.workspace)
    session = get_session(payload.session_id) if payload.session_id else create_session(infer_title(payload.message))
    add_message(session["id"], "user", payload.message)
    result = run_agent(session["id"], payload.message, payload.model or get_default_model(), workspace)
    assistant_message = add_message(session["id"], "assistant", result["reply"])
    session = get_session(session["id"])
    return {
        "session": session,
        "assistant_message": assistant_message,
        "tool_events": result["tool_events"],
        "messages": get_session_messages(session["id"]),
    }


@app.get("/api/memory")
def list_memory() -> list[dict[str, Any]]:
    return db_all("SELECT id, text, created_at FROM memories ORDER BY created_at DESC LIMIT 100")


@app.post("/api/memory")
def create_memory(payload: MemoryRequest) -> dict[str, Any]:
    result = json.loads(save_memory(payload.text))
    return result
