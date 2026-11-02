# Feature 3 - Fitness Chatbot

An always-available AI fitness coach at `/chatbot/` (sidebar item "Coach").
LLM: Groq + Llama 3 (free) or Claude (production). Answers are shaped by a detailed
system prompt and grounded with RAG over a ChromaDB vector store.

## Setup

1. Copy the new/changed files over your project (same folder structure).
2. `pip install -r requirements.txt` (adds `chromadb`).
3. Add to `.env` (see `.env.example`):
   ```ini
   LLM_PROVIDER=groq
   GROQ_API_KEY=your-key-from-console.groq.com
   GROQ_MODEL=llama-3.3-70b-versatile
   ```
   For Claude instead: `LLM_PROVIDER=anthropic`, `ANTHROPIC_API_KEY=...`, `ANTHROPIC_MODEL=...`.
4. `python manage.py migrate`
5. `python manage.py ingest_knowledge` (chunks `chatbot/knowledge/*.md` into `chroma_db/`;
   the first run downloads a small embedding model, ~80 MB).
6. `python manage.py runserver` and open `/chatbot/`.

Add `chroma_db/` to `.gitignore`. Re-run `ingest_knowledge` whenever you add or edit documents.

## How a message flows

`chat.js` -> `POST /chatbot/api/message/` -> `services/coach.py`:
1. `rag.retrieve()` searches the vector DB for the top 4 passages (short follow-ups reuse the previous question).
2. `prompts.build_system_prompt()` = coach instructions + user profile (age/height/weight/goal, no name or email) + retrieved passages.
3. `llm.py` calls Groq or Anthropic with the last 10 messages. The model may call the
   `calculate_nutrition_targets` tool (Mifflin-St Jeor, in `calculators.py`) so calorie and macro
   maths is computed in code, not by the LLM. It asks for sex and activity level first, since the
   profile doesn't store them.
4. Both turns are saved in `ChatMessage`; the reply is returned with the names of the documents used.

## Adding your own reference material

Drop `.md` or `.txt` files in `chatbot/knowledge/` (an `# H1` becomes the title, `##` headings become
chunk boundaries), then run `ingest_knowledge`. The six included documents are concise summaries
written for this project from widely accepted guidance; replace or extend them with your own vetted
sources (papers, guidelines, programme templates) before relying on them.

## Settings (all optional, in `.env`)

| Variable | Default | Purpose |
|---|---|---|
| `RAG_TOP_K` | 4 | Passages retrieved per question |
| `RAG_MAX_DISTANCE` | 0.95 | Cosine-distance cut-off; lower = stricter, raise it if too little context is found |
| `CHAT_RATE_LIMIT_PER_MINUTE` | 15 | Per-user message limit |

If `chromadb` is missing or the vector DB is empty, the app logs a warning and falls back to keyword
(BM25) retrieval, so the chatbot still works.

## Tests

`python manage.py test chatbot` (no API keys or network needed; the LLM is mocked).
