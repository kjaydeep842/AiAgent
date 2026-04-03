# Atlas Agent

Atlas is a proper full-stack AI agent app with a browser UI and a Python backend.

It includes:

- chat sessions with persistent history
- a polished web UI for prompts, sessions, model choice, memory, and tool activity
- OpenAI-compatible API integration with function calling
- workspace tools for file listing, reading, writing, searching, and safe shell commands
- persistent memory and session storage in SQLite
- a project-local workspace safety boundary

## Why this stack

Atlas uses FastAPI for the backend and a lightweight static frontend so it stays easy to run and easy to extend.

For the model layer, Atlas now defaults to `OpenRouter` so you can use free models more easily, while still keeping support for OpenAI-compatible providers.

Sources:

- https://developers.openai.com/api/docs/models
- https://developers.openai.com/api/docs/models/gpt-5.4
- https://developers.openai.com/api/docs/models/gpt-5.4-mini
- https://platform.openai.com/docs/api-reference/responses/compact?api-mode=responses
- https://platform.openai.com/docs/guides/function-calling?api-mode=responses&lang=python
- https://platform.openai.com/docs/guides/text?api-mode=responses

## Project structure

- `main.py` - FastAPI server, provider-aware agent loop, SQLite persistence, API routes
- `static/index.html` - app shell
- `static/styles.css` - UI design and responsive layout
- `static/app.js` - frontend behavior
- `requirements.txt` - Python dependencies
- `.env.example` - required environment variables
- `agent.py` - earlier CLI prototype kept as a simple reference

## Setup

1. Create and activate a virtual environment:

```bash
python3 -m venv .venv
source .venv/bin/activate
```

2. Install dependencies:

```bash
pip install -r requirements.txt
```

3. Create a local `.env` file:

```bash
cp .env.example .env
```

4. Edit `.env` and add your real provider key.

Free default with OpenRouter:

```env
AI_PROVIDER=openrouter
OPENROUTER_API_KEY=your_openrouter_api_key_here
AI_MODEL=openrouter/free
ENABLE_LOCAL_FALLBACK=1
```

If you want OpenAI instead:

```env
AI_PROVIDER=openai
OPENAI_API_KEY=your_openai_api_key_here
AI_MODEL=gpt-5.4-mini
```

## Run the app

```bash
uvicorn main:app --reload
```

Then open `http://127.0.0.1:8000`.

## Current functionality

- create and switch chat sessions
- send prompts to the agent
- inspect tool activity
- store reusable memory
- choose between `gpt-5.4-mini` and `gpt-5.4`
- choose free OpenRouter models or OpenAI models
- use `local-demo` when hosted API quota is unavailable
- set a workspace path inside this project
- use tool-assisted file and command operations

## Notes

- Session and memory data are stored in `data/agent.db`.
- The backend only allows workspace paths that stay inside this project directory.
- Shell commands are intentionally restricted and block destructive commands.
- The app auto-loads variables from `.env`.
- The default free setup uses OpenRouter with `openrouter/free`.
- If provider quota fails, local fallback mode can still return useful starter coding output.
- If you want streaming responses, authentication, file uploads, voice, or image tools next, those can be added on top of this structure.
