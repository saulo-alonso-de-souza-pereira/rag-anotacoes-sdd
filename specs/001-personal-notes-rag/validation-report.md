# Validation Report: Personal Notes RAG

**Date**: 2026-08-18  
**Status**: Automated acceptance passed; moderated usability study executed — SC-002 PASS and
SC-007 FAIL

## Third iteration: LLM-first routing and internal-only semantic retrieval (2026-08-20)

The user explicitly waived retrospective RED/GREEN reconstruction for T143. No pre-implementation
failure evidence was recreated or inferred. The implementation and post-implementation validation
continued from the existing working tree.

### Implemented behavior and targeted validation

- `IntentService.classify` has no regex, keyword, prefix, question-shape or explicit-creation
  extraction path. Every non-empty chat message calls the configured `llama3:latest` adapter first
  and routing occurs only after `IntentDecision` schema validation.
- A valid model decision of `clarification` remains a normal `ChatResponse`. Invalid JSON/schema,
  a disallowed intent or a technical classifier failure after the one same-model repair raises
  `ClassificationError` and maps to the actionable `502 classification_failed` error envelope.
- `general_chat` calls the same model again without retrieval or sources; `rag` alone performs
  owner-filtered internal retrieval and grounded generation; `create_note` and `clarification` do
  not retrieve note context.
- The `/api/v1/search/semantic` router/module, OpenAPI surface, static UI view/menu/form/client call
  and its obsolete contract test were removed. Embeddings, pgvector, indexing jobs, retry-indexing
  and `RetrievalService` remain intact as internal RAG mechanisms.
- Targeted T120-T129 command completed with **39 passed, 1 deselected**. The deselected case was the
  opt-in real-model CPU test; the internal retrieval performance assertion executed and passed.
- The configured non-E2E regression completed with **120 passed, 1 skipped, 9 deselected** and
  **86.25%** branch-aware coverage, above the required 85%.
- Chromium E2E initially exposed three failures caused by the removed `renderSearch` function still
  being called from UI bootstrap. Removing only that residual call fixed the issue; the rerun
  completed with **3 passed, 2 skipped, 125 deselected**.
- Deterministic SC-012 coverage passed in the targeted suite: all four general formulations, their
  explicit RAG counterparts, classifier-override sentinels and valid clarification cases are
  represented. Unit/integration spies prove classification precedes every branch.
- `ruff format --check` reports 90 files formatted and `ruff check` reports no violations.

### Real-backend validation blocked in the resumed managed environment

At that earlier checkpoint, Quickstart 5.3-5.7, the opt-in real-model CPU performance run and the
Compose acceptance run could not be repeated in the resumed managed environment. `docker compose ps` was denied access to both
the user Docker configuration and the Docker Engine named pipe. With the repository-local uv cache,
`scripts/check.ps1` completed frozen dependency checking, formatting and lint, then stopped at
`uv run --frozen alembic heads` because the Python 3.13 executable under the user profile was denied.
Without the local cache it stopped earlier at the global uv cache. These are environment-access
failures, not application test failures.

The user separately confirmed outside this managed environment that Docker was operational, the
application started, health returned 200 and the then-current targeted suite returned 33 passed.
That external confirmation is recorded as user-provided context, not as an execution performed by
this report. At that checkpoint, Quickstart T139 and the complete scripted/opt-in portions of T140
remained objectively blocked until the working tree could be run in that external environment.

### Traceability and Constitution Check

| Scope | Third-iteration tasks/evidence |
|---|---|
| US3, FR-009/010/013/014 | T123, T126, T132, T134, T137-T142; internal indexing/retrieval and grounded-source tests |
| US6, FR-019/022/023 | T120-T133, T138-T141; LLM-first ordering, branch isolation, error and E2E tests |
| SC-004 | T129, T138-T140; internal retrieval test passed, real CPU/Compose rerun blocked |
| SC-012 | T120-T128, T138-T141; deterministic acceptance cases and E2E passed |
| SC-008 | Pre-existing creation tests and requirement unchanged; known creation inconsistency not fixed |

Constitution Check: specification/plan/task traceability, security isolation, fail-closed errors,
typed boundaries, test coverage and static quality gates pass. Final approval remains blocked only
for the real-backend Quickstart, real CPU performance, Compose acceptance and the exact complete
`scripts/check.ps1` run that the managed environment could not access. No commit or push was made.

## Third-iteration Quickstart defect investigation (2026-08-20)

Manual Docker evidence supplied by the user showed that two explicit note questions returned
`classification_failed`, and that a note named `Reunião secreta` existed with the question copied as
content. Docker CLI log access was denied in the managed environment, but the running backend and
Ollama were initially reachable over HTTP. `llama3:latest` resolved to the required digest prefix
`365c0bd3c000`.

Replaying the classifier request isolated the root cause before code changes: the Pydantic-generated
schema sent in Ollama's `format` field could not be converted to a grammar by Ollama 0.30.6. The raw
HTTP response was status 400 with `Failed to initialize samplers: failed to parse grammar`; therefore
there was no model-generated response body for that failed request. The repair call used the same
incompatible schema and could not recover from the grammar initialization failure.

A minimal equivalent schema using an `enum`, required fields and simple nullable types was accepted.
With the corrected schema and strengthened classifier prompt, the raw model response for
`O que eu anotei sobre as decisões tomadas pelo time?` was:

```json
{"needs_clarification":false,"title":null,"content":null,"intent":"rag"}
```

The old prompt with the compatible schema also selected `rag` for both reported questions, but
incorrectly populated `title` and `content`. Cross-field Pydantic validation now rejects those fields
for every non-creation intent and invokes the one allowed same-model repair with both the original
message and prior output. The Ollama-facing schema intentionally excludes unsupported grammar
keywords while `IntentDecision` remains the authoritative strict validator. No regex, keyword,
prefix, question-shape fallback or public semantic-search endpoint was introduced.

The `Reunião secreta` record can only be persisted through a complete `create_note` decision in the
chat path or through the normal Notes API/UI. Historical web logs and database timing were not
accessible, so its exact origin cannot be proven. A prior model misclassification is consistent with
the observed title/content but remains an inference, not a confirmed fact.

Post-fix static validation passed: Ruff formatting, Ruff lint, Python compileall and `git diff
--check`. The directed pytest run could not start because access to the external Python 3.13
executable was denied. After the direct model probes, both the Ollama `/api/ps` endpoint and the app
health endpoint timed out, while Docker Engine access remained denied; consequently the rebuilt
real-Docker flow and full regression could not be executed in this managed environment. At that
checkpoint, T139 and T140 remained unchecked.

## Final pending-validation attempt (2026-08-20)

### T139 — executed, acceptance result FAIL

The running backend was reachable at `http://localhost:18080`; `GET /api/v1/health/live` returned
HTTP 200 with `{"status":"ok"}`. A new isolated validation user was registered and authenticated.
Two notes were created through the Notes API and both reached `semantic_status=ready`:
`Reunião do projeto`, containing the Docker/team-decision fact, and `Minha lista de Compras`.

- `O que eu anotei sobre as decisões tomadas pelo time?` returned HTTP 200 and `intent=rag`, proving
  that the primary classifier selected the RAG branch. Internal retrieval did not clear the fixed
  0.55 threshold, so the response was the documented insufficiency response with `sources=[]`.
  This is the previously diagnosed retrieval limitation; no threshold, embedding or architecture
  setting was changed.
- `Qual é a capital do Peru?` returned HTTP 200, `intent=general_chat`, a substantive general answer,
  `sources=[]` and `created_note=null`, confirming isolation of the general branch from retrieval and
  note creation.
- `POST /api/v1/search/semantic` returned HTTP 404, confirming that public semantic search remains
  absent while note indexing reached `ready` for internal RAG use.
- `Crie uma nota e explique Docker` returned HTTP 200 with `intent=create_note` and persisted exactly
  one note named `Explicação sobre Docker`. This violates the Quickstart 5.6 multiple-intent criterion,
  which requires `intent=clarification` and no write. The record is retained as real validation
  evidence; no classifier or creation correction was made in this validation-only step.
- Deterministic unit/contract/integration evidence from the current revision still distinguishes a
  valid `clarification` response from `502 classification_failed` after the single same-model repair,
  and verifies classifier-first ordering. The live request above nevertheless proves that branch
  isolation is not accepted for every real-model multiple-intent formulation.

T139 is checked because the validation task was executed and its evidence recorded, but its product
acceptance result is **FAIL**. SC-012 and the Quickstart branch-isolation criterion therefore cannot
be declared fully satisfied by this run. The known creation inconsistency remains visible and was
not corrected; the SC-008 requirement and all pre-existing SC-008 assertions remain unchanged.

#### Focused multiple-intent correction

The subsequent correction changed only the instructions supplied to the primary classifier and its
single same-model repair: the model must first identify every requested outcome and give
`clarification` precedence when creation is combined with another incompatible outcome. No message
inspection, heuristic or routing override was added outside the model. A direct, non-persistent
probe of `llama3:latest` using the revised production prompt and the unchanged grammar-compatible
schema classified `Crie uma nota e explique Docker` as:

```json
{"intent":"clarification","title":null,"content":null,"needs_clarification":true}
```

The focused integration matrix covers that case with no retrieval, generation or write; an
unambiguous creation with exactly one write; unambiguous RAG and general chat with no write; and a
genuinely ambiguous request with no write. Execution of those pytest cases remained blocked by the
managed environment's denial of the Python 3.13 executable. T139 remains checked as an executed
validation task; its original failed observation is retained above rather than rewritten. SC-008,
the 0.55 retrieval threshold and the below-threshold experimental observations remain unchanged.

Post-correction validation results: the direct live-model probe passed; Ruff format reported **94
files left unchanged**; Ruff lint passed; Python syntax compilation of the three focused files
passed; and `git diff --check` passed with only the repository's existing LF/CRLF notices. The
directed pytest command was attempted but could not start because the managed account was denied
access to the Python 3.13 executable referenced by `.venv`. The complete `scripts/check.ps1` was
also retried: frozen dependency verification and both Ruff gates passed, then it stopped at
`uv run --frozen alembic heads` with the same permission denial and uv exit code 103. T140 therefore
remains unchecked.

#### LLM-first test-double alignment after the complete-gate failures

The externally executed complete gate reported **5 failed, 123 passed, 1 skipped, 9 deselected**
with **86.35% coverage**. The three RAG integration/evaluation failures used doubles that recognized
classification by searching for the obsolete literal `Classifique`; with the current prompt they
returned the generation payload to `IntentService` instead of a valid `rag` decision. The doubles
now identify the classifier call by the exact `OLLAMA_INTENT_SCHEMA` object and return a valid
`rag` decision before the generation payload. The two unit failures replaced the same literal-string
assertion with observable contract checks: the intent schema is used first, general chat orders
`classify -> generate` without retrieval, and RAG orders `classify -> retrieve -> generate` with a
different structured schema for generation. No production behavior changed.

The prescribed five-test command was attempted first in this managed environment but could not
start collection because `.venv` references the denied external Python 3.13 executable. Ruff
formatted one focused test file and then passed lint for all three; syntax compilation and
`git diff --check` passed. The complete `scripts/check.ps1` retry passed frozen dependency checking
and both Ruff gates, then stopped at `uv run --frozen alembic heads` with the same access denial and
uv exit code 103. Therefore no new final coverage measurement is available here, the latest observed
coverage remains the user-provided **86.35%**, and T140 remains unchecked pending an integral
successful execution.

### T140 — blocked before regression execution

The exact `scripts/check.ps1` gate was attempted with a repository-local uv cache and a process-local
PowerShell execution-policy bypass. Frozen dependency verification passed; Ruff reported **94 files
already formatted** and **all checks passed**. The script then stopped at `uv run --frozen alembic
heads` because the managed account was denied access to
`C:\Users\User\AppData\Local\Programs\Python\Python313\python.exe` (uv exit code 103).

Consequently the script did not reach its pytest, Chromium, opt-in performance, Compose or offline
stages in this final attempt. T140 remains unchecked. The latest successfully completed regression
evidence for this working tree remains **120 passed, 1 skipped, 9 deselected, 86.25% branch-aware
coverage**, plus **3 passed, 2 skipped, 125 deselected** in Chromium E2E. Those earlier results are
not relabeled as a successful final `scripts/check.ps1` run.

### Final Constitution Check

**BLOCKED / product acceptance violation, with no constitutional exception introduced.** The code
structure, owner isolation, fail-closed technical-error path, typed boundaries, internal-only RAG,
coverage above 85%, static quality and traceability evidence remain conformant. Final acceptance is
not PASS because the real-model multiple-intent request created a note instead of asking for
clarification, and because the complete regression/performance/offline gate could not execute under
the managed Python permission restriction. No functional code, model, threshold, architecture,
Specification or Plan change was made during this validation attempt; no commit or push was made.

## Final external validation and closure (2026-08-20)

The complete `scripts/check.ps1` gate was subsequently executed successfully outside the managed
environment against the final working tree. These results were supplied by the user after the local
permission blocks recorded above:

- frozen dependencies: **PASS**;
- Ruff format: **PASS**;
- Ruff lint: **PASS**;
- Alembic: **003 (head)**;
- main suite: **128 passed, 1 skipped, 9 deselected**;
- branch-aware coverage: **86.35%**, satisfying the constitutional minimum of 85%;
- Chromium E2E: **3 passed, 2 skipped, 133 deselected**;
- failures: **0**.

T140 is complete. With T139 already executed and the multiple-intent defect subsequently corrected,
all **143 of 143 tasks** are complete. The earlier failed and environment-blocked observations remain
in this report as chronological evidence and are superseded for final-gate status by this successful
execution.

### Final Constitution Check — PASS

**PASS; no blocking violation and no constitutional exception.** The final implementation preserves
mandatory LLM-first classification through `llama3:latest`; no regex, keyword, prefix, heuristic or
routing bypass decides intent. Multiple incompatible intentions are classified by the model as
`clarification`, with no retrieval, general generation or note write. Public semantic search remains
removed from API and UI, while embeddings, indexing and owner-scoped semantic retrieval remain
internal RAG mechanisms. `embeddinggemma:300m`, the 0.55 threshold, chunking and RAG architecture are
unchanged. SC-008 and its pre-existing assertions are unchanged. The complete automated gate has
zero failures and 86.35% coverage, above the required 85%, so quality, testability, security,
traceability and simplicity gates pass.

The remaining non-blocking experimental limitation is preserved without correction: with
`embeddinggemma:300m` and the fixed 0.55 minimum similarity, some valid RAG queries rank below the
threshold and return the documented insufficiency response. This does not reintroduce public search
and does not alter the final Constitution Check result.

## Residual real-flow multiple-intent correction (2026-08-21)

A subsequent manual run supplied by the user showed that the real application still classified
`Crie uma nota e explique Docker.` as a complete `create_note` decision and persisted a note with
title `Docker` and content `Explique Docker.`. That result demonstrates that the previous single
contrast example was not sufficiently robust in the exercised stack.

Before editing, the managed environment could not reach the application at
`http://localhost:18080` and remained denied access to the Docker Engine, so the exact running web
image and its Ollama service could not be inspected. A direct probe using the current production
prompt/schema against the separately exposed local `llama3:latest` returned this raw classifier
payload even before the change:

```json
{
  "intent": "clarification",
  "title": null,
  "content": null,
  "needs_clarification": true
}
```

Because this differs from the supplied real-application observation, prompt/model-image divergence
between the accessible Ollama instance and the running application remains a material diagnostic
possibility; the exact raw pre-change payload from the unavailable application instance could not be
recovered here. No deterministic intent rule was inferred from that divergence.

The focused change only expands the primary LLM prompt into five symmetric few-shot demonstrations:
simple creation, creation plus general question, creation plus note consultation, general question,
and note consultation. The schema, validator, one-repair fail-closed flow and router are unchanged.
No regex, keyword, prefix, heuristic or pre/post-LLM bypass was added. Against the accessible
`llama3:latest`, the revised prompt returned the raw payload:

```json
{"intent":"clarification","title":null,"content":null,"needs_clarification":true}
```

Ruff format and lint passed and `git diff --check` passed with only existing LF/CRLF notices. The
directed pytest command could not start because access to the Python 3.13 executable referenced by
`.venv` was denied. The `scripts/check.ps1` retry passed frozen dependency verification and both Ruff
gates, then stopped at `uv run --frozen alembic heads` with the same permission denial (uv exit code
103). The mandatory post-change real HTTP checks for multiple intent, simple creation, general chat
and RAG could not run because the application endpoint was unavailable. The previously completed
T139 and T140 checkboxes remain historical completion records, but the final tree now requires an
external rebuilt-stack rerun before this residual correction can be declared accepted end to end.

## Environment

- Windows 11 Pro 10.0.26200, Docker Engine 29.5.3.
- AMD Ryzen 5 4600G, 6 cores/12 logical processors, 16.5 GB RAM, CPU acceptance path.
- Images: `python:3.13.5-slim-bookworm`, `pgvector/pgvector:pg18`, and
  `ollama/ollama:0.30.6`.
- Models: `embeddinggemma:300m` ID `85462619ee72` and `llama3:latest` ID
  `365c0bd3c000`.
- Initial downloads were measured separately from startup: approximately 61.2 s for
  `embeddinggemma:300m` and 424.2 s for `llama3:latest`. Cached model layers were preserved for the
  clean startup trials, as required by SC-009.

## Automated acceptance results

The quality gate in `scripts/check.ps1` validates the frozen lockfile, formatting, lint, the single
Alembic head, unit, contract, integration, security, deterministic RAG evaluation and Chromium E2E
tests. Optional flags add real-model retrieval, CPU performance, three-run Compose and offline
acceptance suites. The default gate passed with 100 tests, 1 environment-dependent test skipped,
6 explicitly deselected tests, 86.16% branch-aware coverage, and 2 Chromium journeys passed.

Real-model evidence:

- Portuguese semantic retrieval evaluation: PASS.
- Ten active sessions, CRUD p95 below 500 ms, semantic-search p95 below 2 s, and at least 9 of 10
  complete chatbot responses within 60 s after an explicit unmeasured model warm-up: PASS.
- Docker internal network reported `Internal=true`; the full search/chat flow passed without external
  model-network access: PASS (89.29 s in the final isolated acceptance run).
- Model initialization executed repeatedly without re-downloading cached models: PASS.

## Three consecutive clean quickstart runs

`tests/e2e/test_compose_quickstart.py` executed three consecutive cycles. Before every cycle it shut
down prior containers and removed only the disposable PostgreSQL acceptance volume; documented
images and model volumes remained available. Each cycle ran startup, migrations, model verification,
registration, canonical-name conflict, invalid and valid login, CSRF rejection, CRUD, optimistic
concurrency, semantic indexing/search, grounded chat with sources, conversational creation,
cross-user GET/PATCH/DELETE/search isolation, permanent deletion, logout, service restart,
persistence verification, and shutdown.

| Run | Startup to ready | Main flow | Restart/persistence | Result |
| --- | ---: | --- | --- | --- |
| 1 | 4.760 s | PASS | PASS | PASS |
| 2 | 4.397 s | PASS | PASS | PASS |
| 3 | 4.469 s | PASS | PASS | PASS |

All startup measurements were below the 15-minute SC-009 limit. The only procedural deviation from a
literal first installation was intentional and required by T093: images and models were already
available, and initial-download time was recorded separately. Browser confirmation/cancellation and
source-link presentation were covered by the Chromium journeys; log inspection was covered by the
redaction suite.

## Moderated usability protocol and results

The study required by T092 was conducted with 10 representative users. It is human-study evidence,
not automated evidence. The study used the following previously defined moderated sequence:

1. Ask the participant to register, log in and create a first note; measure elapsed time from the
   instruction until the note is visible. SC-002 passes only if at least 9 of 10 finish within 3 min.
2. Seed a participant-owned note, ask a question answerable from it, and ask the participant to locate
   the cited source. Record whether the source is found on the first attempt. SC-007 passes only if at
   least 9 of 10 succeed on the first attempt.
3. Record only participant codes `P01` through `P10+`, timings, pass/fail, first-attempt result and
   optional de-identified observations. Do not record names, account credentials or note contents.

### Session script

Before each session, the moderator must verify `/api/v1/health/ready`, create no account for the
participant, reset the browser profile, and prepare one participant-owned seeded note only after the
SC-002 task. A representative participant is an adult who uses browser-based productivity software
at least monthly, has not implemented or tested this feature, and is not shown the interface before
timing begins. Record whether the participant primarily works as a general user, designer,
illustrator, or software developer so the sample composition can be reviewed without identifying the
person.

Read these instructions verbatim, without pointing to controls:

1. **SC-002**: “Crie uma conta, entre no sistema e crie sua primeira anotação com qualquer título e
   conteúdo.” Start the timer after reading the instruction; stop when the created note is visible.
2. Seed a note titled “Reunião do projeto” with content “A reunião será terça-feira às 15 horas” in
   that participant's account and wait until its semantic status is ready.
3. **SC-007**: “Pergunte ao chatbot quando será a reunião do projeto e localize a anotação usada como
   fonte.” Count the first attempt as successful only if the participant opens or clearly identifies
   the displayed source before receiving help.

If a participant asks for help, the moderator may repeat the instruction but must not identify a
control; record the help request as an observation. A technical interruption invalidates that session
and requires a replacement participant rather than recording a failure.

### Anonymized results sheet

| Code | User profile | SC-002 seconds | SC-002 <=180 s | SC-007 first attempt | Valid session | De-identified observation |
| --- | --- | ---: | --- | --- | --- | --- |
| P01 | participante_01 | 60 | Yes | Yes | Yes | First-attempt success without help. |
| P02 | participante_02 | 90 | Yes | Yes | Yes | First-attempt success without help; located source "Lembrete.". |
| P03 | participante_03 | 62 | Yes | No | Yes | Model reported unavailability on first attempt; referenced note found on second attempt. |
| P04 | participante_04 | 51 | Yes | Yes | Yes | First-attempt success. |
| P05 | participante_05 | 61 | Yes | Yes | Yes | First-attempt success. |
| P06 | participante_06 | 51 | Yes | Yes | Yes | First-attempt success. |
| P07 | participante_07 | 52 | Yes | Yes | Yes | First-attempt success. |
| P08 | participante_08 | 49 | Yes | No | Yes | Source found on second attempt after the note was edited. |
| P09 | participante_09 | 48 | Yes | Yes | Yes | First-attempt success. |
| P10 | participante_10 | 58 | Yes | No | Yes | Query had to be specified/refined to locate the source. |

### Consolidated usability outcomes

- **SC-002 — PASS**: 10 of 10 valid participants completed registration, login and first-note
  creation within 3 minutes, a 100% success rate against the required threshold of at least 9 of 10
  (90%). Mean time was 58.2 seconds; minimum was 48 seconds (P09), and maximum was 90 seconds (P02).
- **SC-007 — FAIL**: 7 of 10 valid participants located the source on the first attempt, a 70%
  success rate below the required threshold of at least 9 of 10 (90%). First-attempt successes were
  P01, P02, P04, P05, P06, P07 and P09. First-attempt failures were P03, P08 and P10.

The three SC-007 failures are retained without adjustment: P03 encountered model unavailability and
found the referenced note on the second attempt; P08 found the source on the second attempt after
editing the note; and P10 needed to specify/refine the query to locate the source. T092 is complete
because the study was conducted and documented; its completion does not change SC-007's FAIL result.

## FR/SC traceability

| Requirement | Evidence | Status |
| --- | --- | --- |
| FR-001--FR-004 | Auth domain/API, password/session/security and contract suites | Covered |
| FR-005--FR-009, FR-021 | Owner-scoped persistence, RLS, CRUD/concurrency/cascade and restart tests | Covered |
| FR-010--FR-011 | Indexing/retrieval pipeline, semantic isolation and retrieval evaluation | Covered |
| FR-012--FR-015 | RAG service/API, grounded generation and source-link E2E | Covered |
| FR-016--FR-017 | Strict intent, repair/fail-closed policy, ownership and chat-creation E2E | Covered |
| FR-018--FR-020 | Compose lifecycle, pinned local models, offline and error/redaction tests | Covered |
| SC-001, SC-003--SC-006, SC-008--SC-011 | Security, persistence, RAG, performance, Compose and offline suites | Validated |
| SC-002 | Moderated study above: 10/10 within 3 minutes | Validated — PASS |
| SC-007 | Moderated study above: 7/10 on first attempt | Validated — FAIL |

All 21 functional requirements have implementation and automated-test coverage. The moderated study
validated SC-002 as PASS and SC-007 as FAIL; this failed criterion is not waived or reclassified as an
unexecuted validation.

## Dependency and complexity review

All direct runtime dependencies in `app/pyproject.toml` are imported by application or migration
code; all development dependencies support quality, contracts, browser, database-container, or test
coverage workflows. No dependency or duplicate implementation was removed. Retained complexity is
limited to: separate runtime/migration database roles for least privilege, an indexing worker and
lease-based jobs for durable semantic state, and a strict explicit-field fallback after the model's
single repair attempt to make clear conversational creation deterministic without accepting ambiguous
requests.

## Constitution gate

PASS for implementation structure and automated evidence: the solution remains simple within the
documented constraints, enforces user isolation and secret redaction, exceeds the 85% coverage gate,
keeps requirements/design/implementation separated, and preserves FR/SC-to-test traceability. There
are no justified constitutional violations. The human study was executed, with SC-002 recorded as
PASS and SC-007 recorded as FAIL. The failed success criterion is preserved rather than waived.

The final all-flags invocation of `scripts/check.ps1` completed successfully in 620.5 s. Its
real-model performance suite passed in 138.93 s, its three-run Compose suite in 349.02 s, and its
offline suite in 89.29 s.

## Post-implementation revision: general conversation (2026-08-20)

This section records only the second iteration (T098–T119), which restored the general-conversation
capability omitted from the experiment's base specification. It does not rewrite the first
implementation history, change SC-008, or treat the separately observed creation inconsistency as
part of this correction.

### Routing, contract and implementation evidence

- The response contract and domain accept exactly `rag|general_chat|create_note|clarification`.
- High-confidence intent is decided from the message before retrieval. Explicit references to the
  user's notes route to `rag`; clear definitional questions route to `general_chat`; explicit
  RAG/general ambiguity and explicit multiple-intent connectors route to `clarification`.
- Only `rag` invokes owner-scoped retrieval. An insufficient RAG query returns `intent=rag`, the
  documented insufficiency answer and `sources=[]`; it never falls back to general knowledge.
- `general_chat` invokes the existing `llama3:latest` through the same Ollama adapter, with no note
  context, no sources, no second generative model and no external LLM API. General output is bounded
  to keep complete CPU responses within the existing latency target.
- The UI renders `Resposta geral` for `general_chat` and `Baseada nas suas anotações` only for
  grounded RAG with verified sources.

The prescribed T112 Docker command was executed first against the pre-implementation image and
correctly observed the red state. After rebuilding, its initial unmounted form could not collect the
contract tests because `/specs` is intentionally outside the runtime image. The reproducible
directed run therefore mounted `specs` read-only and disabled only the global full-suite coverage
gate:

```text
docker compose run --rm -v <workspace>/specs:/specs:ro web pytest --no-cov \
  tests/unit/test_intent.py tests/unit/test_rag.py \
  tests/contract/test_chat_contract.py tests/contract/test_chat_creation_contract.py \
  tests/integration/test_chat_modes_flow.py tests/security/test_rag_isolation.py \
  tests/rag_eval/test_intent_quality.py tests/rag_eval/test_conversation_modes_quality.py \
  tests/performance/test_local_targets.py -q
```

Result at the implementation checkpoint: **27 passed, 1 live-model test deselected**. Subsequent
directed runs after real-model findings included 30 routing/orchestration tests and then 29
intent/RAG/Ollama/integration tests; both sets passed.

### Browser, backend and Quickstart acceptance

- Deterministic Chromium journeys: **2 passed** in 1.82 s, covering both indicators, source
  visibility, insufficiency, clarification/non-execution and legacy creation compatibility.
- Real UI → real API → real router → real branch journey: **1 passed, 1 deselected** in 39.77 s.
  The browser observed `Resposta geral` without sources, then a grounded response labeled `Baseada
  nas suas anotações` with a source.
- Quickstart 5.5/5.6 A–H and SC-012 against the real backend: **1 passed** in 137.86 s. The acceptance
  set contained three clear general questions; **3/3 (100%)** returned `general_chat` with
  `sources=[]`, including `O que é Docker?` while a ready Docker note existed. Explicit RAG remained
  RAG, unsupported RAG returned insufficiency without fallback, and ambiguity/multiple intents
  returned clarification without creating a note.
- Model identity inspected in the running Ollama service: `llama3:latest` resolved to
  `365c0bd3c000`; `embeddinggemma:300m` remained `85462619ee72`.

The first real-model acceptance attempts are retained as diagnostic evidence rather than hidden:
one explicit RAG query initially became `clarification`; one multiple-intent message initially became
`create_note`; and an unbounded general response reached the 60-second Ollama timeout and returned
503. The final implementation addressed only these second-iteration routing and general-response
paths. No creation-quality tuning or SC-008 change was made.

### Performance and regression

CPU profile remained the documented AMD Ryzen 5 4600G, 6 cores/12 logical processors and 16.5 GB
RAM. The live performance test covered 10 RAG and 10 general-chat complete responses with the fixed
local model. Final result: **PASS**, 1 test passed in **489.30 s**; each branch satisfied the unchanged
assertion that at least 9 of 10 complete responses finish within 60 seconds. CRUD p95 remained below
500 ms and semantic-search p95 below 2 s in the same run.

The official default gate was then executed through `scripts/check.ps1` with the isolated Python
3.13 environment:

- frozen dependency sync: PASS;
- Ruff format and lint: PASS (96 files formatted consistently, no lint findings);
- Alembic: one head, `003`;
- non-E2E regression: **117 passed, 1 skipped, 9 deselected**, branch-aware coverage **85.90%**;
- default Chromium gate: **3 passed, 2 environment-gated tests skipped, 122 deselected**.

The skip and deselections are the existing marker-controlled live/Compose/offline gates; the live
general-conversation and performance gates were run separately above and passed.

### Second-iteration traceability

| Requirement / outcome | Tasks | Evidence | Result |
| --- | --- | --- | --- |
| US6, FR-022 | T098–T101, T104–T109, T118 | Contract, intent, orchestration and real backend acceptance | PASS |
| FR-011, FR-013 | T100–T102, T108 | Retrieval only in owner-scoped RAG; related note does not select mode | PASS |
| FR-014 | T098, T100–T101, T108, T114 | Unsupported explicit RAG remains insufficient with no general fallback | PASS |
| FR-015 | T098, T100, T103, T109–T110 | Verified RAG sources and grounded UI indicator | PASS |
| FR-023 | T098, T100–T103, T108–T110 | General responses use `sources=[]` and general UI indicator | PASS |
| SC-012 | T104–T105, T112–T114 | 3/3 clear live general questions answered without note-source attribution | PASS |
| Existing CPU latency target | T119, T112, T115 | 10 RAG + 10 general responses; at least 9/10 within 60 s per branch | PASS |
| SC-008 regression boundary | T099, T115, T118 | Historical creation assertions preserved; no creation-quality correction | PRESERVED |

### Constitution Check — second iteration

**PASS; no blocking violation.** Simplicity is preserved by reusing the monolith, endpoint, Ollama
adapter and sole generative model. Security/privacy remain enforced because only the RAG branch can
retrieve owner-scoped notes and general chat receives no note context. Testability is demonstrated by
red-before-green tests, real backend/browser acceptance and coverage above 85%. Rastreability links
US6 and the revised FR/SC set to T098–T119 and the evidence above. Quality is supported by the clean
Ruff/Alembic/regression gates. Requirements, planning and implementation remain separated, and no
Constitution amendment or exception was required.
