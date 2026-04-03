#!/usr/bin/env python3
import argparse
import json
import os
import shlex
import subprocess
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from openai import OpenAI


MAX_FILE_BYTES = 64_000
MAX_COMMAND_OUTPUT = 12_000
MEMORY_FILE = ".agent_memory.json"


SYSTEM_PROMPT = """You are a single general-purpose AI agent for a local workspace.

Your job is to help with many kinds of tasks:
- answer questions
- plan work
- inspect code and files
- search the workspace
- create and update files
- run shell commands when useful
- keep lightweight notes in memory

Guidelines:
- Be practical, concise, and helpful.
- Use tools whenever they make the answer more accurate.
- Prefer searching or reading files over guessing.
- When editing files, keep changes focused and valid.
- Only operate inside the provided workspace.
- Before running a shell command or editing files, briefly explain why in your response.
"""


def ensure_within_workspace(workspace: Path, target: Path) -> Path:
    resolved_workspace = workspace.resolve()
    resolved_target = target.resolve()
    try:
        resolved_target.relative_to(resolved_workspace)
    except ValueError as exc:
        raise ValueError(f"Path must stay inside workspace: {target}") from exc
    return resolved_target


def load_memory(workspace: Path) -> dict[str, Any]:
    memory_path = workspace / MEMORY_FILE
    if not memory_path.exists():
        return {"notes": []}
    try:
        return json.loads(memory_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return {"notes": []}


def save_memory(workspace: Path, data: dict[str, Any]) -> None:
    memory_path = workspace / MEMORY_FILE
    memory_path.write_text(json.dumps(data, indent=2), encoding="utf-8")


def list_files(workspace: Path, relative_dir: str = ".") -> str:
    target = ensure_within_workspace(workspace, workspace / relative_dir)
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
    target = ensure_within_workspace(workspace, workspace / relative_path)
    if not target.exists():
        return json.dumps({"error": f"File not found: {relative_path}"})
    if not target.is_file():
        return json.dumps({"error": f"Not a file: {relative_path}"})
    size = target.stat().st_size
    if size > MAX_FILE_BYTES:
        return json.dumps(
            {
                "error": f"File too large to read directly ({size} bytes).",
                "max_bytes": MAX_FILE_BYTES,
            }
        )
    return target.read_text(encoding="utf-8", errors="replace")


def write_file(workspace: Path, relative_path: str, content: str, mode: str = "overwrite") -> str:
    target = ensure_within_workspace(workspace, workspace / relative_path)
    target.parent.mkdir(parents=True, exist_ok=True)

    if mode == "append":
        with target.open("a", encoding="utf-8") as handle:
            handle.write(content)
    else:
        target.write_text(content, encoding="utf-8")

    return json.dumps({"status": "ok", "path": str(target.relative_to(workspace)), "mode": mode})


def search_workspace(workspace: Path, pattern: str) -> str:
    matches = []
    for path in workspace.rglob("*"):
        if not path.is_file():
            continue
        relative = str(path.relative_to(workspace))
        if pattern.lower() in relative.lower():
            matches.append({"path": relative, "match_type": "path"})
            continue
        try:
            text = path.read_text(encoding="utf-8", errors="ignore")
        except OSError:
            continue
        if pattern.lower() in text.lower():
            matches.append({"path": relative, "match_type": "content"})

        if len(matches) >= 50:
            break

    return json.dumps({"pattern": pattern, "matches": matches}, indent=2)


def run_command(workspace: Path, command: str) -> str:
    blocked = {"rm", "sudo", "shutdown", "reboot", "mkfs", "dd"}
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
    output = (result.stdout or "") + (result.stderr or "")
    trimmed = output[:MAX_COMMAND_OUTPUT]
    return json.dumps(
        {
            "command": command,
            "exit_code": result.returncode,
            "output": trimmed,
            "truncated": len(output) > len(trimmed),
        },
        indent=2,
    )


def save_note(workspace: Path, note: str) -> str:
    memory = load_memory(workspace)
    memory.setdefault("notes", [])
    memory["notes"].append(
        {
            "note": note,
            "created_at": datetime.now(timezone.utc).isoformat(),
        }
    )
    save_memory(workspace, memory)
    return json.dumps({"status": "saved", "note": note})


def get_memory(workspace: Path) -> str:
    return json.dumps(load_memory(workspace), indent=2)


def get_time() -> str:
    now = datetime.now().astimezone()
    return json.dumps(
        {
            "local_time": now.isoformat(),
            "utc_time": datetime.now(timezone.utc).isoformat(),
        },
        indent=2,
    )


TOOLS = [
    {
        "type": "function",
        "name": "list_files",
        "description": "List files and folders inside a workspace directory.",
        "parameters": {
            "type": "object",
            "properties": {
                "relative_dir": {
                    "type": "string",
                    "description": "Directory path relative to the workspace root.",
                }
            },
            "additionalProperties": False,
        },
        "strict": True,
    },
    {
        "type": "function",
        "name": "read_file",
        "description": "Read a UTF-8 text file inside the workspace.",
        "parameters": {
            "type": "object",
            "properties": {
                "relative_path": {
                    "type": "string",
                    "description": "File path relative to the workspace root.",
                }
            },
            "required": ["relative_path"],
            "additionalProperties": False,
        },
        "strict": True,
    },
    {
        "type": "function",
        "name": "write_file",
        "description": "Create or update a text file inside the workspace.",
        "parameters": {
            "type": "object",
            "properties": {
                "relative_path": {
                    "type": "string",
                    "description": "File path relative to the workspace root.",
                },
                "content": {
                    "type": "string",
                    "description": "The full content to write.",
                },
                "mode": {
                    "type": "string",
                    "enum": ["overwrite", "append"],
                    "description": "Whether to overwrite or append.",
                },
            },
            "required": ["relative_path", "content", "mode"],
            "additionalProperties": False,
        },
        "strict": True,
    },
    {
        "type": "function",
        "name": "search_workspace",
        "description": "Search file paths and file contents in the workspace.",
        "parameters": {
            "type": "object",
            "properties": {
                "pattern": {
                    "type": "string",
                    "description": "Case-insensitive search string.",
                }
            },
            "required": ["pattern"],
            "additionalProperties": False,
        },
        "strict": True,
    },
    {
        "type": "function",
        "name": "run_command",
        "description": "Run a non-destructive shell command from the workspace.",
        "parameters": {
            "type": "object",
            "properties": {
                "command": {
                    "type": "string",
                    "description": "Shell command to run.",
                }
            },
            "required": ["command"],
            "additionalProperties": False,
        },
        "strict": True,
    },
    {
        "type": "function",
        "name": "save_note",
        "description": "Save a short memory note for later turns.",
        "parameters": {
            "type": "object",
            "properties": {
                "note": {
                    "type": "string",
                    "description": "A note to remember.",
                }
            },
            "required": ["note"],
            "additionalProperties": False,
        },
        "strict": True,
    },
    {
        "type": "function",
        "name": "get_memory",
        "description": "Load saved memory notes.",
        "parameters": {
            "type": "object",
            "properties": {},
            "additionalProperties": False,
        },
        "strict": True,
    },
    {
        "type": "function",
        "name": "get_time",
        "description": "Get the current local and UTC time.",
        "parameters": {
            "type": "object",
            "properties": {},
            "additionalProperties": False,
        },
        "strict": True,
    },
]


def execute_tool(workspace: Path, name: str, args: dict[str, Any]) -> str:
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
    if name == "save_note":
        return save_note(workspace, args["note"])
    if name == "get_memory":
        return get_memory(workspace)
    if name == "get_time":
        return get_time()
    return json.dumps({"error": f"Unknown tool: {name}"})


def extract_text(response: Any) -> str:
    text = getattr(response, "output_text", "")
    if text:
        return text

    chunks = []
    for item in getattr(response, "output", []):
        if getattr(item, "type", "") != "message":
            continue
        for content in getattr(item, "content", []):
            if getattr(content, "type", "") == "output_text":
                chunks.append(content.text)
    return "\n".join(chunks).strip()


def agent_loop(client: OpenAI, model: str, workspace: Path, user_message: str) -> str:
    conversation: list[dict[str, Any]] = [
        {"role": "system", "content": SYSTEM_PROMPT},
        {
            "role": "user",
            "content": (
                f"Workspace root: {workspace}\n"
                f"User request: {user_message}"
            ),
        },
    ]

    for _ in range(8):
        response = client.responses.create(model=model, input=conversation, tools=TOOLS)

        tool_outputs = []
        for item in getattr(response, "output", []):
            if getattr(item, "type", "") != "function_call":
                continue
            args = json.loads(item.arguments)
            result = execute_tool(workspace, item.name, args)
            tool_outputs.append(
                {
                    "type": "function_call_output",
                    "call_id": item.call_id,
                    "output": result,
                }
            )

        if not tool_outputs:
            return extract_text(response)

        conversation.extend(tool_outputs)

    return "The agent stopped after several tool rounds. Please refine the request and try again."


def repl(client: OpenAI, model: str, workspace: Path) -> None:
    print(f"General AI agent ready in {workspace}")
    print("Type 'exit' to quit.\n")
    while True:
        try:
            user_message = input("You: ").strip()
        except EOFError:
            print()
            break
        if not user_message:
            continue
        if user_message.lower() in {"exit", "quit"}:
            break
        reply = agent_loop(client, model, workspace, user_message)
        print(f"\nAgent: {reply}\n")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="General-purpose local AI agent")
    parser.add_argument(
        "--model",
        default=os.getenv("OPENAI_MODEL", "gpt-5.4-mini"),
        help="OpenAI model to use. Default: OPENAI_MODEL or gpt-5.4-mini",
    )
    parser.add_argument(
        "--workspace",
        default=".",
        help="Workspace directory the agent can access.",
    )
    parser.add_argument(
        "--prompt",
        help="Run a single request instead of interactive mode.",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    if not os.getenv("OPENAI_API_KEY"):
        raise SystemExit("Missing OPENAI_API_KEY. Add it to your environment first.")

    workspace = Path(args.workspace).resolve()
    workspace.mkdir(parents=True, exist_ok=True)

    client = OpenAI()
    if args.prompt:
        print(agent_loop(client, args.model, workspace, args.prompt))
        return

    repl(client, args.model, workspace)


if __name__ == "__main__":
    main()
