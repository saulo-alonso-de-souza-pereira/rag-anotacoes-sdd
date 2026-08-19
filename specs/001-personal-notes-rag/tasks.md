---

description: "Dependency-ordered implementation tasks for personal notes RAG"
---

# Tasks: Gerenciamento de Anotações Pessoais com RAG

**Input**: Design documents from `/specs/001-personal-notes-rag/`

**Prerequisites**: `plan.md`, `spec.md`, `research.md`, `data-model.md`, `contracts/openapi.yaml`,
`quickstart.md`

**Tests**: Required by the project constitution for business rules, security boundaries, critical
behavior, contracts, persistence, RAG quality, and acceptance criteria. Test tasks appear before the
implementation they verify and must fail for the expected reason before implementation begins.

**Organization**: Tasks are grouped by prioritized user story so each story can be implemented and
validated as an incremental slice.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel with adjacent tasks after its prerequisites are complete
- **[Story]**: Maps work to one specification user story
- Every task names an exact target file or directory

## Phase 1: Setup (Shared Infrastructure)

**Purpose**: Initialize the planned single Python project and deterministic development tooling.

- [X] T001 Create the planned package and test directory tree with package markers under `app/src/notes_rag/` and `app/tests/`
- [X] T002 Define Python 3.13 runtime and pinned application/test dependencies in `app/pyproject.toml`
- [X] T003 Generate and commit the deterministic dependency lock in `app/uv.lock`
- [X] T004 Configure Ruff linting, formatting, pytest markers, and coverage thresholds in `app/pyproject.toml`
- [X] T005 [P] Create non-secret environment defaults and validation documentation in `.env.example`
- [X] T006 [P] Add repository exclusions for local secrets, caches, coverage, and generated artifacts in `.gitignore`
- [X] T007 Create shared pytest markers, deterministic clock/UUID fixtures, and test configuration in `app/tests/conftest.py`
- [X] T008 [P] Create the static UI shell and accessibility landmarks in `app/src/notes_rag/web/index.html`

**Checkpoint**: Dependencies install from the lockfile, tests discover successfully, and no application
behavior has been implemented.

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: Establish configuration, database boundaries, API infrastructure, safe errors, and
replaceable local-model integration required by every story.

**⚠️ CRITICAL**: No user story implementation starts until this phase passes its foundational tests.

- [X] T009 [P] Write unit tests for environment parsing, required secrets, model IDs, and safe defaults in `app/tests/unit/test_config.py`
- [X] T010 [P] Write contract tests that validate `specs/001-personal-notes-rag/contracts/openapi.yaml` as OpenAPI 3.1 and assert security declarations in `app/tests/contract/test_openapi_document.py`
- [X] T011 [P] Write unit tests for uniform error envelopes and sensitive-detail redaction in `app/tests/unit/test_api_errors.py`
- [X] T012 Implement typed configuration for database, cookies, CSRF, Ollama, model identity, retrieval, and worker settings in `app/src/notes_rag/config.py`
- [X] T013 [P] Implement async SQLAlchemy engine, session factory, transaction helpers, and separate runtime/migration role configuration in `app/src/notes_rag/persistence/database.py`
- [X] T014 [P] Implement request IDs, safe error mapping, `Cache-Control: no-store`, and exception handlers in `app/src/notes_rag/api/errors.py`
- [X] T015 [P] Define the Ollama completion/embedding port, typed responses, timeouts, and sanitized adapter errors in `app/src/notes_rag/llm/ollama.py`
- [X] T016 Assemble versioned API routers, middleware ordering, static assets, readiness, and lifespan hooks in `app/src/notes_rag/main.py`
- [X] T017 Add foundational smoke tests for application startup, readiness failure, request IDs, and static UI serving in `app/tests/integration/test_application_foundation.py`

**Checkpoint**: Foundation is ready; story phases can begin, with later stories depending only on the
specific earlier domain capability stated below.

---

## Phase 3: User Story 1 - Gerenciar anotações pessoais com segurança (Priority: P1) 🎯 MVP

**Goal**: Register and authenticate users and provide isolated, persistent create/list/read/update/delete
operations for title-and-content notes, including permanent confirmed deletion.

**Independent Test**: Create Alice and Bob, authenticate separately, exercise all five note operations,
restart persistence, and prove neither can observe or mutate the other's notes.

### Tests for User Story 1

- [X] T018 [P] [US1] Write unit tests for username canonicalization, password rules, Argon2id verify/rehash, and generic authentication failures in `app/tests/unit/test_users.py`
- [X] T019 [P] [US1] Write unit tests for note title/content validation, version increments, semantic reset, and deletion rules in `app/tests/unit/test_notes.py`
- [X] T020 [P] [US1] Write contract tests for register, login, logout, current-user, and auth error responses from OpenAPI in `app/tests/contract/test_auth_contract.py`
- [X] T021 [P] [US1] Write contract tests for note CRUD, pagination, `If-Match`, validation, and indistinguishable 404 responses in `app/tests/contract/test_notes_contract.py`
- [X] T022 [P] [US1] Write integration tests for concurrent canonical username uniqueness and session create/expire/revoke lifecycle in `app/tests/integration/test_auth_persistence.py`
- [X] T023 [P] [US1] Write integration tests for CRUD transactions, optimistic concurrency, permanent deletion, and restart persistence in `app/tests/integration/test_notes_persistence.py`
- [X] T024 [P] [US1] Write the anonymous/owner/other-user authorization matrix for every auth and note operation in `app/tests/security/test_note_isolation.py`
- [X] T025 [P] [US1] Write security tests for CSRF/origin checks, cookie flags, credential enumeration, rate limiting, and secret-free logs in `app/tests/security/test_session_security.py`

### Implementation for User Story 1

- [X] T026 [P] [US1] Implement User and Session domain validation and state transitions in `app/src/notes_rag/domain/users.py`
- [X] T027 [P] [US1] Implement Note validation, semantic status, versioning, and permanent-delete rules in `app/src/notes_rag/domain/notes.py`
- [X] T028 [US1] Define User, Session, and Note persistence mappings and constraints in `app/src/notes_rag/persistence/models.py`
- [X] T029 [US1] Create the initial PostgreSQL schema, pgvector extension, User/Session/Note constraints, and Note RLS policies in `app/migrations/versions/001_users_sessions_notes.py`
- [X] T030 [US1] Implement transaction-local RLS user context and default-deny assertions in `app/src/notes_rag/persistence/rls.py`
- [X] T031 [US1] Implement owner-scoped User, Session, and Note repositories with cursor pagination and `(id,user_id)` lookups in `app/src/notes_rag/persistence/repositories.py`
- [X] T032 [US1] Implement Argon2id hashing, opaque session rotation/revocation, CSRF validation, throttling, and generic failures in `app/src/notes_rag/services/authentication.py`
- [X] T033 [US1] Implement note CRUD, optimistic version checks, and atomic permanent deletion in `app/src/notes_rag/services/notes.py`
- [X] T034 [US1] Implement register/login/logout/current-user endpoints and protected-session dependency in `app/src/notes_rag/api/auth.py`
- [X] T035 [US1] Implement note create/list/read/update/delete endpoints and safe error mappings in `app/src/notes_rag/api/notes.py`
- [X] T036 [P] [US1] Implement accessible registration, login, logout, note list/editor, conflict handling, and deletion confirmation in `app/src/notes_rag/web/app.js`
- [X] T037 [P] [US1] Style authentication, note management, validation, focus, and preparation-state components in `app/src/notes_rag/web/styles.css`
- [X] T038 [US1] Add browser E2E coverage for registration through CRUD, canceled/confirmed deletion, logout, and restart persistence in `app/tests/e2e/test_notes_journey.py`

**Checkpoint**: US1 is a secure, persistent MVP and all US1 tests pass independently without semantic
search or chatbot behavior.

---

## Phase 4: User Story 2 - Recuperar anotações por significado (Priority: P2)

**Goal**: Prepare current note content within 30 seconds and retrieve only the authenticated user's
semantically relevant notes without exact textual matching.

**Independent Test**: Index controlled Alice/Bob corpora, query paraphrases, verify Recall@5 and the
30-second state transition, and prove cross-user trap notes never enter results.

### Tests for User Story 2

- [X] T039 [P] [US2] Write unit tests for title/content chunking, paragraph boundaries, 350-token target, overlap, and empty-chunk rejection in `app/tests/unit/test_chunking.py`
- [X] T040 [P] [US2] Write unit tests for indexing job leases, retry backoff, obsolete versions, and state transitions in `app/tests/unit/test_indexing.py`
- [X] T041 [P] [US2] Write contract tests for semantic search and retry-indexing schemas/status codes in `app/tests/contract/test_search_contract.py`
- [X] T042 [P] [US2] Write PostgreSQL/pgvector integration tests for atomic enqueue/publish/delete, worker recovery, and pending-to-ready within 30 seconds in `app/tests/integration/test_indexing_pipeline.py`
- [X] T043 [P] [US2] Write security tests proving pre-filtered retrieval and zero cross-user chunks/results under adversarial similarity in `app/tests/security/test_semantic_isolation.py`
- [X] T044 [P] [US2] Create the fixed Portuguese semantic corpus, paraphrase queries, and expected relevance judgments in `app/tests/rag_eval/fixtures/retrieval_cases.json`

### Implementation for User Story 2

- [X] T045 [P] [US2] Implement NoteChunk and IndexingJob domain rules and lease states in `app/src/notes_rag/domain/indexing.py`
- [X] T046 [US2] Extend persistence mappings with NoteChunk vector(768) and IndexingJob constraints in `app/src/notes_rag/persistence/models.py`
- [X] T047 [US2] Add NoteChunk/IndexingJob tables, indexes, cascades, and forced RLS policies in `app/migrations/versions/002_semantic_indexing.py`
- [X] T048 [US2] Extend note writes to enqueue versioned indexing jobs atomically and add worker repositories in `app/src/notes_rag/persistence/repositories.py`
- [X] T049 [US2] Implement deterministic chunking, embedding calls, leased job processing, atomic publication, retries, and stale-version rejection in `app/src/notes_rag/services/indexing.py`
- [X] T050 [US2] Implement the polling worker lifecycle and graceful lease release in `app/src/notes_rag/worker.py`
- [X] T051 [US2] Implement exact cosine retrieval with mandatory owner/status/version filters, top-k, threshold, and note deduplication in `app/src/notes_rag/services/retrieval.py`
- [X] T052 [US2] Implement semantic search and retry-indexing endpoints in `app/src/notes_rag/api/search.py` and `app/src/notes_rag/api/notes.py`
- [X] T053 [US2] Add semantic status polling, retry action, search form, empty state, and source-result rendering in `app/src/notes_rag/web/app.js`
- [X] T054 [US2] Implement Recall@5, unrelated-query, and 30-second SLA evaluation assertions in `app/tests/rag_eval/test_retrieval_quality.py`

**Checkpoint**: US2 can be demonstrated over US1 notes without any generative response, and its
retrieval/isolation tests pass independently.

---

## Phase 5: User Story 3 - Consultar anotações pelo chatbot (Priority: P3)

**Goal**: Answer natural-language questions exclusively from authorized retrieved notes, expose verified
sources, and state insufficiency when context does not support an answer.

**Independent Test**: Ask answerable and unanswerable questions against a controlled per-user corpus;
verify grounding, source IDs/titles/excerpts, prompt-injection resistance, and zero cross-user influence.

### Tests for User Story 3

- [X] T055 [P] [US3] Write unit tests for context delimiters, prompt-injection treatment, insufficiency prompts, citation parsing, and source deduplication in `app/tests/unit/test_rag.py`
- [X] T056 [P] [US3] Write contract tests for answer, insufficient-context, source, validation, and model-unavailable chat responses in `app/tests/contract/test_chat_contract.py`
- [X] T057 [P] [US3] Write integration tests with a deterministic Ollama fake for retrieval-to-prompt-to-response flow and invented-citation rejection in `app/tests/integration/test_rag_flow.py`
- [X] T058 [P] [US3] Write security tests for cross-user context exclusion and malicious instructions embedded in notes in `app/tests/security/test_rag_isolation.py`
- [X] T059 [P] [US3] Create grounded, unsupported, conflicting, and injection evaluation cases in `app/tests/rag_eval/fixtures/generation_cases.json`

### Implementation for User Story 3

- [X] T060 [P] [US3] Implement ChatResponse, Source, and safe citation domain types in `app/src/notes_rag/domain/chat.py`
- [X] T061 [US3] Implement context budgeting for the 8192-token Llama 3 window, restrictive Portuguese prompt construction, and insufficiency handling in `app/src/notes_rag/services/rag.py`
- [X] T062 [US3] Implement `llama3:latest` completion calls, timeout handling, and expected-ID verification in `app/src/notes_rag/llm/ollama.py`
- [X] T063 [US3] Implement backend citation validation and source reconstruction solely from retrieved chunks in `app/src/notes_rag/services/rag.py`
- [X] T064 [US3] Implement authenticated non-streaming question/answer behavior for `/api/v1/chat/messages` in `app/src/notes_rag/api/chat.py`
- [X] T065 [US3] Implement accessible chatbot message, loading, insufficiency, error, and clickable-source UI in `app/src/notes_rag/web/app.js`
- [X] T066 [US3] Implement groundedness, source completeness, unsupported-answer, and prompt-injection evaluations in `app/tests/rag_eval/test_generation_quality.py`

**Checkpoint**: US3 answers from notes with verified sources or declines for insufficient context; it does
not yet create notes from chat.

---

## Phase 6: User Story 4 - Criar anotação por conversa (Priority: P4)

**Goal**: Interpret a natural-language creation request using the single experimental model, safely
persist exactly one valid note, or request clarification without writing.

**Independent Test**: Submit clear, incomplete, ambiguous, malformed-model, and ordinary-question cases;
verify exact-once creation, session-derived ownership, one repair limit, confirmation, and persistence.

### Tests for User Story 4

- [X] T067 [P] [US4] Write unit tests for strict intent schema validation, completion parsing, one repair attempt, and fail-closed clarification in `app/tests/unit/test_intent.py`
- [X] T068 [P] [US4] Write contract tests for `create_note`, `needs_clarification`, and `created_note` chat response variants in `app/tests/contract/test_chat_creation_contract.py`
- [X] T069 [P] [US4] Write integration tests proving exactly-one transactional creation, ordinary questions create nothing, and restart persistence in `app/tests/integration/test_chat_note_creation.py`
- [X] T070 [P] [US4] Write security tests proving message/payload owner IDs are ignored and ownership always comes from the session in `app/tests/security/test_chat_creation_ownership.py`
- [X] T071 [P] [US4] Add clear, incomplete, mixed-intent, malformed-JSON, and repair evaluation cases in `app/tests/rag_eval/fixtures/intent_cases.json`

### Implementation for User Story 4

- [X] T072 [US4] Implement the strict `answer|create_note` completion schema, temperature-zero request, parse, single repair, and fail-closed policy in `app/src/notes_rag/services/intent.py`
- [X] T073 [US4] Extend chat orchestration to invoke the ordinary Note service with session ownership only after valid intent in `app/src/notes_rag/services/rag.py`
- [X] T074 [US4] Extend `/api/v1/chat/messages` to return clarification or created-note confirmation without exposing model internals in `app/src/notes_rag/api/chat.py`
- [X] T075 [US4] Add clarification prompts and created-note confirmation/link behavior to the chatbot in `app/src/notes_rag/web/app.js`
- [X] T076 [US4] Implement intent accuracy, exact-once creation, malformed-output, and no-accidental-write evaluations in `app/tests/rag_eval/test_intent_quality.py`
- [X] T077 [US4] Add browser E2E coverage for clear creation, missing fields, ordinary question, and persisted note discovery in `app/tests/e2e/test_chat_creation_journey.py`

**Checkpoint**: US4 adds safe conversational creation without tool calling or a second generative model.

---

## Phase 7: User Story 5 - Executar o fluxo principal de forma reproduzível (Priority: P5)

**Goal**: Build and run web, worker, PostgreSQL/pgvector, and Ollama reproducibly with persistent data and
models, CPU baseline, experimental model identity enforcement, and no external LLM API dependency.

**Independent Test**: On a compatible clean environment, follow only `quickstart.md`, start within 15
minutes after downloads, complete the main flow offline, restart, and confirm persistent data/models.

### Tests for User Story 5

- [X] T078 [P] [US5] Write static container-policy tests for pinned images, non-root app user, healthchecks, volumes, secret exclusions, and four required services in `app/tests/contract/test_container_configuration.py`
- [X] T079 [P] [US5] Write integration tests for migration idempotency, startup ordering, worker lease recovery, and volume-backed restart persistence in `app/tests/integration/test_container_lifecycle.py`
- [X] T080 [P] [US5] Write tests that reject a `llama3:latest` resolution other than `365c0bd3c000` and confirm `embeddinggemma:300m` remains configured in `app/tests/integration/test_model_baseline.py`
- [X] T081 [P] [US5] Write an offline acceptance test proving search/chat perform no external LLM API calls after model download in `app/tests/e2e/test_offline_flow.py`

### Implementation for User Story 5

- [X] T082 [P] [US5] Create the multi-stage, non-root Python application image for web/tests/worker in `Dockerfile`
- [X] T083 [P] [US5] Create idempotent migration and model-initialization entry scripts in `scripts/migrate.ps1` and `scripts/pull-models.ps1`
- [X] T084 [US5] Define `web`, `index-worker`, `db`, `ollama`, `migrate`, and `model-init` services, healthchecks, named volumes, and CPU defaults in `compose.yaml`
- [X] T085 [US5] Add optional Windows/WSL2 GPU profile overrides without changing the CPU acceptance path in `compose.gpu.yaml`
- [X] T086 [US5] Implement model-init verification for `llama3:latest` ID `365c0bd3c000` and pinned embedding digest in `scripts/pull-models.ps1`
- [X] T087 [US5] Add end-to-end Compose orchestration coverage for build, migrate, model init, main flow, restart, and shutdown, and execute it in three consecutive runs in a clean environment to validate SC-009 in `app/tests/e2e/test_compose_quickstart.py`
- [X] T088 [US5] Record exact CPU/GPU prerequisites, first-download behavior, safe startup, and non-destructive shutdown commands in `README.md`

**Checkpoint**: The complete flow is reproducible, local, persistent, and independently verifiable from
a clean compatible environment.

---

## Phase 8: Polish & Cross-Cutting Concerns

**Purpose**: Validate measurable outcomes and security/maintainability gates across completed stories.

- [X] T089 [P] Add load scenarios for CRUD p95 <500 ms, semantic search p95 <2 s, at least 90% of complete chatbot responses presented within 60 s on the documented CPU profile, and 10 active sessions in `app/tests/performance/test_local_targets.py`
- [X] T090 [P] Add log-capture tests proving passwords, cookies, CSRF tokens, note bodies, chunks, prompts, and raw model output are redacted in `app/tests/security/test_log_redaction.py`
- [X] T091 [P] Add dependency, migration, OpenAPI, and configuration consistency checks to the local quality script in `scripts/check.ps1`
- [X] T092 Define and conduct a moderated usability study with at least 10 representative users, measuring SC-002 (at least 9 of 10 complete registration, login, and first-note creation within 3 minutes) and SC-007 (at least 9 of 10 locate the sources on the first attempt), and record the protocol and anonymized results in `specs/001-personal-notes-rag/validation-report.md`
- [X] T093 Execute every scenario in `specs/001-personal-notes-rag/quickstart.md` in three consecutive runs in a clean environment with documented prerequisites, images, and models already available; measure startup from the first documented startup command until the complete main flow is ready, and record startup duration, initial-download duration separately, hardware, results, and deviations in `specs/001-personal-notes-rag/validation-report.md`
- [X] T094 Review task-to-FR/SC traceability and record final coverage in `specs/001-personal-notes-rag/validation-report.md`
- [X] T095 Remove unused dependencies/code, resolve duplication, and document any retained complexity in `app/pyproject.toml` and `specs/001-personal-notes-rag/validation-report.md`
- [X] T096 Run the complete unit, contract, integration, security, E2E, performance, and RAG-eval suites via `scripts/check.ps1`
- [X] T097 Re-run the constitution gate and record PASS evidence or explicit justified violations in `specs/001-personal-notes-rag/validation-report.md`

---

## Dependencies & Execution Order

### Phase Dependencies

- **Phase 1 Setup**: Starts immediately.
- **Phase 2 Foundational**: Depends on Phase 1 and blocks all stories.
- **US1 (Phase 3)**: Depends only on Foundation; produces the MVP and ownership/authentication base.
- **US2 (Phase 4)**: Depends on Foundation and the Note aggregate/service from US1.
- **US3 (Phase 5)**: Depends on US2 retrieval and US1 authentication.
- **US4 (Phase 6)**: Depends on US3 chat endpoint/orchestration and US1 Note service.
- **US5 (Phase 7)**: Container artifacts can begin after Foundation, but its acceptance tests require
  US1–US4 complete.
- **Polish (Phase 8)**: Depends on every story included in the release.

### User Story Dependency Graph

```text
Setup --> Foundation --> US1 (MVP) --> US2 --> US3 --> US4
                       \                         /
                        +------> US5 build -----+
                                      |
                         all stories -> Polish
```

### Within Each User Story

1. Write the story's tests and verify they fail for the missing behavior.
2. Add domain/persistence structures before dependent services.
3. Implement services before endpoints and UI integration.
4. Run the story-specific unit, contract, integration, security, E2E, and eval tests.
5. Stop at the checkpoint if any acceptance criterion fails.

### Parallel Opportunities

- Setup T005–T006 and T008 can run in parallel after T001/T002 as applicable; T004 runs after T002
  because both modify `app/pyproject.toml`.
- Foundation tests T009–T011 can run in parallel; T013–T015 touch separate modules.
- Tests marked `[P]` within each story can be authored concurrently before implementation.
- Domain modules and UI styling marked `[P]` touch separate files.
- US5 image and scripts (T082–T083) can start after Foundation while US2–US4 proceed, but Compose
  acceptance waits for all behaviors.
- Polish tests T089–T091 can be authored in parallel after their relevant stories exist.

---

## Parallel Examples

### User Story 1

```text
T018 test users/passwords   | T019 test notes/domain
T020 auth contract          | T021 notes contract
T022 auth persistence       | T023 notes persistence
T024 isolation matrix       | T025 session security
```

### User Story 2

```text
T039 chunking tests         | T040 worker-state tests
T041 search contract        | T042 indexing integration
T043 semantic isolation     | T044 Portuguese corpus
```

### User Story 3

```text
T055 RAG unit tests         | T056 chat contract
T057 RAG integration        | T058 RAG security
T059 generation eval cases
```

### User Story 4

```text
T067 intent unit tests      | T068 creation contract
T069 creation integration  | T070 ownership security
T071 intent eval cases
```

### User Story 5

```text
T078 container policy       | T079 lifecycle integration
T080 model baseline         | T081 offline flow
T082 Dockerfile             | T083 init scripts
```

---

## Implementation Strategy

### MVP First

1. Complete Setup and Foundation.
2. Complete US1 and all its tests.
3. Stop and validate secure two-user CRUD plus persistence independently.
4. Demonstrate the MVP before adding semantic/model infrastructure.

### Incremental Delivery

1. **US1**: secure persistent notes.
2. **US2**: semantic preparation and retrieval, independently demonstrable without generation.
3. **US3**: grounded question answering and verified sources.
4. **US4**: conversational note creation with fail-closed completion parsing.
5. **US5**: complete reproducible local packaging and offline/restart acceptance.
6. **Polish**: measurable quality, traceability, and constitution gates.

### Commit Discipline

- Commit after each task or cohesive test/implementation pair.
- Do not mark a task complete until its relevant tests pass.
- Never bypass failing isolation, credential, source, deletion, or model-baseline tests.
- Update planning artifacts before implementing any newly discovered requirement or architectural change.

## Notes

- `[P]` means file-level independence, not permission to ignore listed prerequisites.
- `[USn]` provides traceability to the prioritized specification story.
- `llama3:latest` is the only generative model; its observed ID must remain `365c0bd3c000` for the
  controlled experiment. `embeddinggemma:300m` remains the embedding model.
- The backend, never the model or client, determines ownership and public sources.
- No task introduces external document ingestion, attachments, chat-history persistence, a second LLM,
  dedicated broker, separate vector database, or approximate index.
