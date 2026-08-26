# DealGoblin AI Deal Analyst Implementation Plan

> **For agentic workers:** REQUIRED: Use superpowers:subagent-driven-development (if subagents available) or superpowers:executing-plans to implement this plan. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Upgrade DealGoblin from a Telegram flea-market search and alert bot into an AI-powered marketplace analyst that extracts structured deal data, supports hybrid search, scores deal quality, sends explainable alerts, and reports eval metrics.

**Architecture:** Keep the current Telethon ingestion, SQLite/FTS5 storage, aiogram bot, and matcher as the stable spine. Add an AI layer behind small repo-owned interfaces: extraction after message insert, optional vector indexing beside SQLite/FTS5, deal scoring before notification, and eval/observability tooling that can run without production Telegram state.

**Tech Stack:** Python 3.13, uv, Telethon, aiogram v3, aiosqlite, SQLite/FTS5, Pydantic, pytest, ruff, bandit, pip-audit. New AI dependencies are selected per phase after checking current provider/vector-store docs with Context7.

---

## Scope

This plan is based on the attached "AI Deal Analyst for Telegram Marketplaces" brief and the current DealGoblin repo shape.

Current repo path:

- `/Users/tamaramalysheva/PycharmProjects/DealGoblin`

Current app spine:

- `src/dealgoblin/ingest/collector.py` inserts normalized Telegram messages.
- `src/dealgoblin/storage/schema.py` owns SQLite schema.
- `src/dealgoblin/storage/repo.py` owns repository operations.
- `src/dealgoblin/match/matcher.py` creates match events from watches.
- `src/dealgoblin/bot/notifier.py` sends match alerts.
- `src/dealgoblin/__main__.py` wires runtime components.

Non-goals for the first release:

- No fine-tuning.
- No image/OCR support.
- No multi-agent system.
- No live local testing with production Telegram bot tokens or production Telethon sessions.
- No replacement of SQLite/FTS5; vector search is additive.

## Implementation Rules

- Before implementing provider-specific LLM, embedding, Qdrant, Chroma, aiogram, or Telethon API calls, use Context7: resolve the library ID, then query docs for the exact integration question.
- Keep secrets in environment variables only. Do not commit API keys, Telegram tokens, sessions, databases, or local eval captures that contain private chat content.
- Keep AI runtime optional behind settings so existing search/alert behavior works without an LLM key.
- Add tests for every behavior change. Prefer fake LLM/vector clients in tests.
- Run the smallest relevant test first, then the local gate from `docs/agents/commands.md`.

## File Map

Planned new files:

- `src/dealgoblin/ai/__init__.py` - package marker and public AI exports.
- `src/dealgoblin/ai/models.py` - Pydantic models for extracted posts, scores, risks, search intents, and eval records.
- `src/dealgoblin/ai/client.py` - provider-agnostic LLM protocol and provider implementation boundary.
- `src/dealgoblin/ai/extraction.py` - post extraction orchestration, validation, retry/failure handling.
- `src/dealgoblin/ai/embeddings.py` - embedding protocol and provider wrapper.
- `src/dealgoblin/ai/vector_store.py` - vector-store protocol plus selected local implementation.
- `src/dealgoblin/ai/hybrid_search.py` - merge/rank SQLite FTS results with vector similarity results.
- `src/dealgoblin/ai/scoring.py` - deterministic deal scoring from extraction, price, risk, duplicates, and watch match.
- `src/dealgoblin/ai/assistant.py` - natural-language search/watchlist intent parsing.
- `src/dealgoblin/observability.py` - trace IDs, structured events, counters, and dev capture helpers.
- `evals/extraction_cases.jsonl` - manually labeled extraction evals.
- `evals/search_cases.jsonl` - manually labeled search evals.
- `evals/scoring_cases.jsonl` - manually labeled scoring evals.
- `evals/run_evals.py` - offline eval runner.
- `evals/report.md` - latest eval result summary.
- `docs/architecture.md` - architecture summary for README and release notes.
- `tests/test_ai_models.py` - schema validation tests.
- `tests/test_ai_extraction.py` - extraction orchestration tests with fake LLM.
- `tests/test_ai_storage.py` - extraction/vector/deal score persistence tests.
- `tests/test_ai_hybrid_search.py` - FTS plus vector ranking tests.
- `tests/test_ai_scoring.py` - deal score and risk flag tests.
- `tests/test_ai_assistant.py` - natural-language watchlist/search tests.
- `tests/test_ai_evals.py` - eval runner metric tests.
- `tests/test_observability.py` - trace and counter tests.

Planned modified files:

- `pyproject.toml` - add only the selected AI/vector dependencies.
- `README.md` - reposition as DealGoblin AI after metrics exist.
- `docs/agents/commands.md` - add eval command only after `evals/run_evals.py` exists.
- `src/dealgoblin/config.py` - add optional AI settings.
- `src/dealgoblin/storage/schema.py` - add extraction, scoring, vector metadata, and run-log tables.
- `src/dealgoblin/storage/repo.py` - add focused repos for extracted posts, AI runs, deal scores, and vector metadata.
- `src/dealgoblin/ingest/collector.py` - keep insert behavior, expose row ID for AI processing through existing `on_ingest`.
- `src/dealgoblin/match/matcher.py` - incorporate deal score/risk when available without breaking FTS watch matching.
- `src/dealgoblin/bot/notifier.py` - send explainable alert text when score data exists, fallback to current text otherwise.
- `src/dealgoblin/bot/handlers.py` and `src/dealgoblin/bot/handlers_keywords.py` - add natural-language search/watchlist entry points when assistant is ready.
- `src/dealgoblin/__main__.py` - wire optional AI services into `on_ingest`.

## Phase 0 - Portfolio And Product Positioning

Purpose: make the project readable as a portfolio-grade AI engineering project before changing runtime behavior.

### Task 0.1: Capture the product target in repo docs

**Files:**
- Create: `docs/ai-deal-analyst.md`
- Modify: `README.md`

- [ ] **Step 1: Add product brief**

Create `docs/ai-deal-analyst.md` with:

```markdown
# AI Deal Analyst

DealGoblin AI watches allowlisted Telegram marketplace chats, extracts structured item data from noisy posts, indexes lexical and semantic signals, scores deal quality, and sends explainable alerts.

## First Release

- Structured post extraction
- Eval suite with quality, cost, and latency metrics
- Hybrid SQLite/FTS5 plus vector search
- Deal scoring with risk flags
- Explainable alert messages

## Later

- Image parsing
- Price history
- Web dashboard
- Tool interface
```

- [ ] **Step 2: Keep README current-state honest**

Update `README.md` with a short "Roadmap" section pointing to `docs/ai-deal-analyst.md`. Do not claim AI behavior exists until implemented and measured.

- [ ] **Step 3: Verify docs render and links are valid**

Run:

```bash
uv run ruff format --check src/ tests/
```

Expected: command passes or reports only existing formatting issues unrelated to docs.

- [ ] **Step 4: Commit**

```bash
git add README.md docs/ai-deal-analyst.md
git commit -m "docs: add ai deal analyst roadmap"
```

### Task 0.2: Do out-of-repo GitHub profile cleanup

**Files:**
- No repo files.

- [ ] Pin the strongest repos: `DealGoblin`, `own_harness`, `ForgettingCurveBot`, `scoring-api`.
- [ ] Unpin or archive weak/tutorial-looking repos that distract from backend/AI engineering.
- [ ] Update profile headline to: `Python Backend Engineer building AI systems with async bots, LLM agents, RAG, evals, and production deployment.`
- [ ] Add current focus bullets: LLM applications, RAG plus evals, async Python services, AI agents with tool use.

## Phase 1 - AI Foundation And Structured Extraction

Purpose: add typed extraction without changing user-facing alerts yet.

### Task 1.1: Add AI settings and data models

**Files:**
- Create: `src/dealgoblin/ai/__init__.py`
- Create: `src/dealgoblin/ai/models.py`
- Modify: `src/dealgoblin/config.py`
- Test: `tests/test_ai_models.py`
- Test: `tests/test_config.py`

- [ ] **Step 1: Write model tests**

Add tests that prove:

- `ExtractedPost` accepts partial marketplace posts.
- `ExtractedPost` rejects negative prices.
- `RiskFlag` has stable string codes.
- Optional AI settings do not become required for default runtime startup.

- [ ] **Step 2: Add minimal models**

Implement models shaped like:

```python
from pydantic import BaseModel, Field


class RiskFlag(BaseModel):
    code: str = Field(min_length=1)
    reason: str = Field(min_length=1)


class ExtractedPost(BaseModel):
    title: str | None = None
    category: str | None = None
    brand: str | None = None
    model: str | None = None
    price: float | None = Field(default=None, ge=0)
    currency: str | None = None
    condition: str | None = None
    location: str | None = None
    seller_signal: str | None = None
    risk_flags: list[RiskFlag] = Field(default_factory=list)
    summary: str | None = None
```

- [ ] **Step 3: Add optional settings**

Add to `Settings`:

```python
ai_enabled: bool = False
llm_provider: str = "disabled"
llm_model: str | None = None
llm_api_key: str | None = None
llm_timeout_seconds: float = 20.0
llm_max_retries: int = 1
```

Validate positive timeout and non-negative retries.

- [ ] **Step 4: Run focused tests**

```bash
uv run pytest tests/test_ai_models.py tests/test_config.py -q
```

Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add src/dealgoblin/ai/__init__.py src/dealgoblin/ai/models.py src/dealgoblin/config.py tests/test_ai_models.py tests/test_config.py
git commit -m "feat: add ai extraction models and settings"
```

### Task 1.2: Add provider-agnostic extraction boundary

**Files:**
- Create: `src/dealgoblin/ai/client.py`
- Create: `src/dealgoblin/ai/extraction.py`
- Test: `tests/test_ai_extraction.py`

- [ ] **Step 1: Use Context7 for selected LLM SDK docs**

Resolve and query the selected provider SDK before importing it. Capture the chosen package and version in the implementation PR notes.

- [ ] **Step 2: Write fake-client extraction tests**

Test cases:

- valid JSON becomes `ExtractedPost`
- malformed JSON is marked failed
- schema-invalid JSON is marked failed
- timeout/provider exception is marked failed
- no API key with `ai_enabled=false` does not call provider

- [ ] **Step 3: Add client protocol and result wrapper**

Define a narrow protocol:

```python
from typing import Protocol


class LLMClient(Protocol):
    async def extract_post(self, raw_text: str) -> str:
        ...
```

Keep provider-specific SDK calls behind this protocol.

- [ ] **Step 4: Add extraction orchestration**

`extract_post_data(raw_text: str, client: LLMClient) -> ExtractionResult` should parse JSON, validate `ExtractedPost`, and preserve failure reason.

- [ ] **Step 5: Run focused tests**

```bash
uv run pytest tests/test_ai_extraction.py -q
```

Expected: PASS.

- [ ] **Step 6: Commit**

```bash
git add src/dealgoblin/ai/client.py src/dealgoblin/ai/extraction.py tests/test_ai_extraction.py
git commit -m "feat: add ai extraction boundary"
```

## Phase 2 - Persistence And Ingestion Integration

Purpose: save AI extraction output for each ingested message while preserving current FTS alerts.

### Task 2.1: Add AI persistence tables and repos

**Files:**
- Modify: `src/dealgoblin/storage/schema.py`
- Modify: `src/dealgoblin/storage/repo.py`
- Test: `tests/test_ai_storage.py`

- [ ] **Step 1: Write storage tests**

Test:

- saving extraction success for a message row ID
- saving extraction failure reason for a message row ID
- upsert behavior on retry
- fetching extraction by message row ID

- [ ] **Step 2: Add tables**

Add schema for:

```sql
CREATE TABLE IF NOT EXISTS ai_extractions (
    message_rowid INTEGER PRIMARY KEY REFERENCES messages(rowid) ON DELETE CASCADE,
    status TEXT NOT NULL,
    provider TEXT,
    model TEXT,
    extracted_json TEXT,
    error_code TEXT,
    error_message TEXT,
    cost_usd REAL,
    latency_ms INTEGER,
    created_at TEXT NOT NULL DEFAULT (datetime('now')),
    updated_at TEXT NOT NULL DEFAULT (datetime('now'))
);
```

- [ ] **Step 3: Add focused repo**

Add `AIExtractionRepo` with:

- `save_success(message_rowid, provider, model, extracted_json, cost_usd, latency_ms)`
- `save_failure(message_rowid, provider, model, error_code, error_message, latency_ms)`
- `get_by_message_rowid(message_rowid)`

- [ ] **Step 4: Run focused tests**

```bash
uv run pytest tests/test_ai_storage.py -q
```

Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add src/dealgoblin/storage/schema.py src/dealgoblin/storage/repo.py tests/test_ai_storage.py
git commit -m "feat: persist ai extraction results"
```

### Task 2.2: Wire optional extraction into runtime

**Files:**
- Modify: `src/dealgoblin/__main__.py`
- Modify: `src/dealgoblin/ingest/collector.py` only if the existing `on_ingest` hook is insufficient.
- Test: `tests/test_integration.py`
- Test: `tests/test_runtime_setup.py`

- [ ] **Step 1: Add integration tests with fake extractor**

Prove:

- current matching still runs when `ai_enabled=false`
- extraction runs after message insert when `ai_enabled=true`
- extraction failure does not block FTS matching

- [ ] **Step 2: Wire in `on_ingest`**

In `src/dealgoblin/__main__.py`, call extraction before or beside `evaluate_message`, but do not make notification depend on extraction yet.

- [ ] **Step 3: Run focused tests**

```bash
uv run pytest tests/test_integration.py tests/test_runtime_setup.py -q
```

Expected: PASS.

- [ ] **Step 4: Commit**

```bash
git add src/dealgoblin/__main__.py src/dealgoblin/ingest/collector.py tests/test_integration.py tests/test_runtime_setup.py
git commit -m "feat: run optional ai extraction on ingest"
```

## Phase 3 - Evals Before More AI Features

Purpose: make quality measurable before adding semantic search and scoring.

### Task 3.1: Add extraction eval dataset and runner

**Files:**
- Create: `evals/extraction_cases.jsonl`
- Create: `evals/run_evals.py`
- Create: `evals/report.md`
- Test: `tests/test_ai_evals.py`
- Modify: `docs/agents/commands.md`

- [ ] **Step 1: Write eval metric tests**

Test:

- exact field match accuracy
- valid JSON rate
- invalid JSON rate
- average latency aggregation
- average cost aggregation

- [ ] **Step 2: Add 20 to 30 labeled cases**

Use sanitized marketplace-like examples. Do not include private seller identifiers or raw private chat dumps.

- [ ] **Step 3: Implement runner**

`uv run python evals/run_evals.py --suite extraction --offline` should run against checked-in expected outputs and fake or fixture responses.

- [ ] **Step 4: Generate first report**

`evals/report.md` should include:

```markdown
| Metric | Result |
|---|---:|
| Valid JSON rate | generated by eval runner |
| Extraction field accuracy | generated by eval runner |
| Invalid JSON rate | generated by eval runner |
| Avg cost/post | generated by eval runner |
| p95 latency | generated by eval runner |
```

- [ ] **Step 5: Add command canon entry**

Add to `docs/agents/commands.md`:

```bash
uv run python evals/run_evals.py --suite extraction
```

- [ ] **Step 6: Run focused tests**

```bash
uv run pytest tests/test_ai_evals.py -q
```

Expected: PASS.

- [ ] **Step 7: Commit**

```bash
git add evals/extraction_cases.jsonl evals/run_evals.py evals/report.md tests/test_ai_evals.py docs/agents/commands.md
git commit -m "feat: add extraction eval suite"
```

## Phase 4 - Embeddings And Hybrid Search

Purpose: add semantic retrieval without losing current phrase/minus-word FTS behavior.

### Task 4.1: Add vector-store boundary

**Files:**
- Create: `src/dealgoblin/ai/embeddings.py`
- Create: `src/dealgoblin/ai/vector_store.py`
- Modify: `pyproject.toml`
- Test: `tests/test_ai_hybrid_search.py`

- [ ] **Step 1: Choose vector backend**

Use Context7 to compare the current Python docs for the selected vector backend. Prefer local development simplicity. Document why `Qdrant` or `Chroma` was chosen in PR notes.

- [ ] **Step 2: Write fake vector tests**

Tests should not require a running external service unless the backend is explicitly local/in-memory.

- [ ] **Step 3: Add protocols**

Define:

```python
class EmbeddingClient(Protocol):
    async def embed_text(self, text: str) -> list[float]:
        ...


class VectorStore(Protocol):
    async def upsert_message(self, message_rowid: int, vector: list[float]) -> None:
        ...

    async def search(self, vector: list[float], limit: int) -> list[VectorHit]:
        ...
```

- [ ] **Step 4: Run focused tests**

```bash
uv run pytest tests/test_ai_hybrid_search.py -q
```

Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add pyproject.toml uv.lock src/dealgoblin/ai/embeddings.py src/dealgoblin/ai/vector_store.py tests/test_ai_hybrid_search.py
git commit -m "feat: add vector search boundary"
```

### Task 4.2: Add hybrid search

**Files:**
- Create: `src/dealgoblin/ai/hybrid_search.py`
- Modify: `src/dealgoblin/storage/repo.py`
- Test: `tests/test_ai_hybrid_search.py`
- Create: `evals/search_cases.jsonl`

- [ ] **Step 1: Test ranking merge**

Cover:

- FTS-only result
- vector-only result
- overlapping result boosted once
- deterministic ordering for equal scores

- [ ] **Step 2: Implement hybrid search**

Keep SQLite/FTS5 as the lexical source and merge vector hits with a small scoring function. Do not remove `MessageRepo.search_fts`.

- [ ] **Step 3: Add search eval cases**

Start with 10 to 20 sanitized search examples.

- [ ] **Step 4: Run focused tests**

```bash
uv run pytest tests/test_ai_hybrid_search.py tests/test_ai_evals.py -q
```

Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add src/dealgoblin/ai/hybrid_search.py src/dealgoblin/storage/repo.py tests/test_ai_hybrid_search.py evals/search_cases.jsonl
git commit -m "feat: add hybrid semantic search"
```

## Phase 5 - Deal Scoring And Explainable Alerts

Purpose: turn extraction/search into useful user-facing alerts with confidence and risk.

### Task 5.1: Add deal scoring

**Files:**
- Create: `src/dealgoblin/ai/scoring.py`
- Modify: `src/dealgoblin/storage/schema.py`
- Modify: `src/dealgoblin/storage/repo.py`
- Modify: `src/dealgoblin/match/matcher.py`
- Create: `evals/scoring_cases.jsonl`
- Test: `tests/test_ai_scoring.py`
- Test: `tests/test_match.py`

- [ ] **Step 1: Write scoring tests**

Cover:

- below-comparable price improves score
- missing price lowers confidence
- duplicate/repost risk lowers score
- risk flags are preserved
- existing FTS watch matching still works without extraction

- [ ] **Step 2: Add score model**

Add `DealScore` in `src/dealgoblin/ai/models.py`:

```python
class DealScore(BaseModel):
    confidence: float = Field(ge=0, le=1)
    price_attractiveness: float = Field(ge=0, le=1)
    info_completeness: float = Field(ge=0, le=1)
    seller_risk: float = Field(ge=0, le=1)
    duplicate_risk: float = Field(ge=0, le=1)
    reasoning: list[str] = Field(default_factory=list)
```

- [ ] **Step 3: Persist scores**

Add `deal_scores` table keyed by `message_rowid`, with JSON reasoning and timestamps.

- [ ] **Step 4: Run focused tests**

```bash
uv run pytest tests/test_ai_scoring.py tests/test_match.py -q
```

Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add src/dealgoblin/ai/models.py src/dealgoblin/ai/scoring.py src/dealgoblin/storage/schema.py src/dealgoblin/storage/repo.py src/dealgoblin/match/matcher.py evals/scoring_cases.jsonl tests/test_ai_scoring.py tests/test_match.py
git commit -m "feat: score deal quality"
```

### Task 5.2: Add explainable alert messages

**Files:**
- Modify: `src/dealgoblin/bot/notifier.py`
- Test: `tests/test_notifier.py`

- [ ] **Step 1: Write notifier tests**

Cover:

- AI score available: alert includes item title, price, why, risk, confidence, and link.
- AI score missing: alert falls back to current `Match: ...` message.
- Send failure behavior still backs off.

- [ ] **Step 2: Implement formatter**

Keep formatting in a small helper function inside `notifier.py` or a new `src/dealgoblin/bot/alert_text.py` if tests become easier.

- [ ] **Step 3: Run focused tests**

```bash
uv run pytest tests/test_notifier.py -q
```

Expected: PASS.

- [ ] **Step 4: Commit**

```bash
git add src/dealgoblin/bot/notifier.py tests/test_notifier.py
git commit -m "feat: send explainable deal alerts"
```

## Phase 6 - Natural-Language Search And Watchlists

Purpose: let users ask for marketplace intent in natural language and map it to structured search/watch filters.

### Task 6.1: Add search intent parser

**Files:**
- Create: `src/dealgoblin/ai/assistant.py`
- Modify: `src/dealgoblin/ai/models.py`
- Test: `tests/test_ai_assistant.py`

- [ ] **Step 1: Write intent parser tests**

Examples:

- "Find a washing machine under 20000, not LG or Samsung, pickup this week"
- "Best used MacBook Air deal this week"
- Missing budget should return a follow-up question.

- [ ] **Step 2: Add models**

Add `SearchIntent` with include terms, excluded brands/terms, price range, category, timeframe, location, and follow-up question.

- [ ] **Step 3: Implement parser behind LLM protocol**

Use the same provider boundary style as extraction. Validation failures should return a controlled error, not crash handlers.

- [ ] **Step 4: Run focused tests**

```bash
uv run pytest tests/test_ai_assistant.py -q
```

Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add src/dealgoblin/ai/assistant.py src/dealgoblin/ai/models.py tests/test_ai_assistant.py
git commit -m "feat: parse natural language search intent"
```

### Task 6.2: Wire assistant into bot handlers

**Files:**
- Modify: `src/dealgoblin/bot/handlers.py`
- Modify: `src/dealgoblin/bot/handlers_keywords.py`
- Modify: `src/dealgoblin/match/fts_query.py` if structured exclusions need reuse.
- Test: `tests/test_bot.py`

- [ ] **Step 1: Write bot handler tests**

Cover:

- user asks natural-language search and receives top results
- user asks to create a watchlist and stored watch uses structured filters
- parser asks follow-up when budget/category is missing

- [ ] **Step 2: Add handler flow**

Keep existing keyword menu behavior working. Add assistant entry points without replacing existing explicit watch creation.

- [ ] **Step 3: Run focused tests**

```bash
uv run pytest tests/test_bot.py tests/test_ai_assistant.py -q
```

Expected: PASS.

- [ ] **Step 4: Commit**

```bash
git add src/dealgoblin/bot/handlers.py src/dealgoblin/bot/handlers_keywords.py src/dealgoblin/match/fts_query.py tests/test_bot.py
git commit -m "feat: add natural language marketplace search"
```

## Phase 7 - Observability, README Polish, And Release

Purpose: make the project credible as production-oriented AI software.

### Task 7.1: Add AI observability

**Files:**
- Create: `src/dealgoblin/observability.py`
- Modify: `src/dealgoblin/__main__.py`
- Modify: `src/dealgoblin/ai/extraction.py`
- Modify: `src/dealgoblin/ai/scoring.py`
- Test: `tests/test_observability.py`

- [ ] **Step 1: Write observability tests**

Cover:

- trace ID generated per message
- error categories are stable strings
- dev capture only writes when explicitly enabled
- counters can report posts processed, alerts sent, invalid extraction rate, cost, and latency

- [ ] **Step 2: Add error categories**

Use stable codes:

- `invalid_json`
- `schema_invalid`
- `extraction_failed`
- `duplicate_detected`
- `alert_suppressed`
- `llm_timeout`

- [ ] **Step 3: Add dev capture setting**

If raw LLM input/output capture is added, store it only under a local configured path and default it off.

- [ ] **Step 4: Run focused tests**

```bash
uv run pytest tests/test_observability.py tests/test_ai_extraction.py tests/test_ai_scoring.py -q
```

Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add src/dealgoblin/observability.py src/dealgoblin/__main__.py src/dealgoblin/ai/extraction.py src/dealgoblin/ai/scoring.py tests/test_observability.py
git commit -m "feat: add ai observability"
```

### Task 7.2: Publish README with measured results

**Files:**
- Modify: `README.md`
- Modify: `evals/report.md`
- Create: `docs/architecture.md`

- [ ] **Step 1: Run full evals**

```bash
uv run python evals/run_evals.py --suite all
```

Expected: report updates with measured numbers.

- [ ] **Step 2: Update README structure**

Use these sections:

- Problem
- Solution
- Architecture
- AI Features
- Eval Results
- Failure Modes
- How to Run
- Roadmap

- [ ] **Step 3: Add architecture summary**

Create `docs/architecture.md` with the runtime flow:

```markdown
# Architecture

Telegram sources -> Telethon collector -> SQLite messages and FTS5 -> AI extraction -> optional vector index -> matcher and deal scoring -> aiogram notifier -> eval and observability reports.
```

- [ ] **Step 4: Add only real numbers**

Do not copy aspirational metrics from the brief. Publish measured values from `evals/report.md`.

- [ ] **Step 5: Run local gate**

```bash
uv run ruff format --check src/ tests/
uv run ruff check src/ tests/
uv run pytest -q
uv run bandit -q -r src/dealgoblin -ll -ii
uv export --frozen --format requirements.txt --extra dev --no-emit-project --output-file /tmp/requirements-deps.txt
uv run pip-audit --strict -r /tmp/requirements-deps.txt --no-deps
```

Expected: PASS.

- [ ] **Step 6: Commit**

```bash
git add README.md evals/report.md docs/architecture.md
git commit -m "docs: publish ai deal analyst results"
```

### Task 7.3: Release portfolio version

**Files:**
- No source files unless release notes are added.

- [ ] Open 3 to 5 GitHub issues for later roadmap items: image parsing, price history, web dashboard, MCP/tool interface.
- [ ] Create a clean release tag after CI passes on `main`:

```bash
git tag v0.1-ai
git push origin v0.1-ai
```

## Four-Week Milestone Map

Week 1:

- Phase 0 complete.
- Phase 1 complete.
- At least 20 extraction eval cases drafted.

Week 2:

- Phase 2 complete.
- Phase 3 complete.
- README still honest: roadmap plus first eval report, no unsupported claims.

Week 3:

- Phase 4 complete.
- Phase 5 complete.
- Alerts include score/reason/risk when AI data exists.

Week 4:

- Phase 6 complete if time allows.
- Phase 7 complete.
- Architecture docs, demo media, release tag, and GitHub issues created.

## Release Gate

Before merging the AI release branch:

```bash
uv run ruff format --check src/ tests/
uv run ruff check src/ tests/
uv run pytest -q
uv run bandit -q -r src/dealgoblin -ll -ii
uv export --frozen --format requirements.txt --extra dev --no-emit-project --output-file /tmp/requirements-deps.txt
uv run pip-audit --strict -r /tmp/requirements-deps.txt --no-deps
uv run python evals/run_evals.py --suite all
```

Expected:

- Existing non-AI bot behavior still passes.
- AI features are optional when `AI_ENABLED=false`.
- Eval report contains measured values.
- No secrets or production Telegram state are committed.
- README claims match implemented behavior and measured evals.
