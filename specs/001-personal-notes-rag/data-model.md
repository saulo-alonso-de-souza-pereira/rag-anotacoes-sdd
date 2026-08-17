# Data Model: Gerenciamento de Anotações Pessoais com RAG

## Conventions

- Identificadores internos são UUIDs gerados pelo servidor e nunca conferem autorização por si só.
- Instantes usam UTC e são serializados em ISO 8601.
- `user_id` é derivado da sessão autenticada, nunca aceito do cliente ou do modelo.
- Tabelas com dados pessoais usam filtros explícitos e Row-Level Security (RLS) com default deny.
- Texto de senha, token de sessão, prompts internos e respostas brutas de modelo não são persistidos.
- Exclusão de nota é física e transacional; não existe estado de lixeira.

## Entity: User

Representa a conta e a identidade proprietária de notas.

| Field | Type | Required | Rules |
|-------|------|----------|-------|
| `id` | UUID | yes | Primary key, server-generated |
| `username` | text | yes | Display form; trimmed; length 3–64 |
| `username_canonical` | text | yes | Trim + Unicode casefold; globally unique |
| `password_hash` | text | yes | Encoded Argon2id hash including salt/parameters |
| `created_at` | timestamp | yes | Immutable UTC instant |
| `updated_at` | timestamp | yes | UTC instant |

**Invariants**:

- Password plaintext exists only during request processing and is never logged or stored.
- Username conflict is enforced by a database unique constraint, including concurrent registration.
- Password length baseline is 12–128 Unicode characters; no composition rules. This is an
  implementation-level security default and may be revised by a recorded policy decision.

**Relationships**: One user owns zero or more sessions, notes and indexing jobs.

## Entity: Session

Represents a revocable authenticated browser session.

| Field | Type | Required | Rules |
|-------|------|----------|-------|
| `id` | UUID | yes | Primary key |
| `user_id` | UUID | yes | Foreign key to User; indexed |
| `token_hash` | bytes/text | yes | Unique hash of random token; raw token only in cookie |
| `csrf_token_hash` | bytes/text | yes | Hash used to validate state-changing requests |
| `created_at` | timestamp | yes | UTC instant |
| `last_seen_at` | timestamp | yes | Updated with bounded frequency |
| `expires_at` | timestamp | yes | Absolute expiry; initial baseline 24 hours |
| `revoked_at` | timestamp | no | Set at logout or security revocation |

**Valid session**: token hash matches, `revoked_at` is null and `expires_at` is in the future.

**State transitions**:

```text
created/active --> expired
       |
       +-------> revoked
```

Expired and revoked rows may be deleted by periodic maintenance. Authentication responses are
generic whether username, password or session is invalid.

## Entity: Note

Represents one permanently owned personal annotation.

| Field | Type | Required | Rules |
|-------|------|----------|-------|
| `id` | UUID | yes | Primary key, server-generated |
| `user_id` | UUID | yes | Foreign key to User; immutable; indexed |
| `title` | text | yes | Trimmed; length 1–200 |
| `content` | text | yes | Non-blank; length 1–100,000 |
| `version` | integer | yes | Starts at 1; increments on title/content update |
| `semantic_status` | enum | yes | `pending`, `processing`, `ready`, `failed` |
| `semantic_error_code` | text | no | Safe code only; present for `failed` |
| `semantic_updated_at` | timestamp | no | Last semantic state transition |
| `created_at` | timestamp | yes | Immutable UTC instant |
| `updated_at` | timestamp | yes | UTC instant |

**Invariants**:

- All reads/writes require `(id, user_id)` ownership match.
- Create persists version 1 with `pending` and an indexing job in one transaction.
- Update validates the final title/content, increments version, sets `pending` and replaces any
  outstanding job for the previous version in the same transaction.
- Delete physically removes note, chunks and jobs in one transaction. Foreign keys use cascade only
  within this ownership aggregate.
- A note is semantically searchable only when `semantic_status=ready` and its chunks match `version`.

**State transitions**:

```text
create/update --> pending --> processing --> ready
                    ^            |
                    |            +-------> failed --> pending (retry)
                    +---- newer note version invalidates prior work

any existing state --> permanently deleted (after confirmed request)
```

## Entity: NoteChunk

Represents retrievable content derived from exactly one version of a note.

| Field | Type | Required | Rules |
|-------|------|----------|-------|
| `id` | UUID | yes | Primary key |
| `note_id` | UUID | yes | Foreign key to Note, cascade delete |
| `user_id` | UUID | yes | Must equal owning Note user; indexed and protected by RLS |
| `note_version` | integer | yes | Must match Note version before publication |
| `ordinal` | integer | yes | Zero-based order within note; unique per note/version |
| `text` | text | yes | Title plus content segment; non-blank |
| `token_count` | integer | yes | Positive diagnostic value |
| `embedding` | vector(768) | yes | Produced by pinned embedding model |
| `embedding_model` | text | yes | Model identifier/digest used |
| `created_at` | timestamp | yes | UTC instant |

**Invariants**:

- Worker builds replacement chunks before atomically replacing the ready set.
- Retrieval always includes `user_id=current_user` and joins only a `ready` Note of matching version.
- No approximate vector index is required initially. B-tree indexes cover `user_id`, `note_id` and
  `(note_id, note_version, ordinal)`.

## Entity: IndexingJob

Durable transactional request to prepare one note version.

| Field | Type | Required | Rules |
|-------|------|----------|-------|
| `id` | UUID | yes | Primary key |
| `note_id` | UUID | yes | Foreign key to Note, cascade delete |
| `user_id` | UUID | yes | Must equal Note owner; indexed/RLS |
| `note_version` | integer | yes | Unique active job per note version |
| `status` | enum | yes | `pending`, `processing`, `retry_wait`, `failed`, `completed` |
| `attempt_count` | integer | yes | Starts at 0; bounded maximum 5 |
| `available_at` | timestamp | yes | Retry/poll eligibility |
| `claimed_at` | timestamp | no | Lease start |
| `lease_expires_at` | timestamp | no | Allows recovery after worker death |
| `last_error_code` | text | no | Sanitized operational code |
| `created_at` | timestamp | yes | Used to measure 30-second SLA |
| `completed_at` | timestamp | no | Completion instant |

**Processing rules**:

1. Worker claims eligible rows using `FOR UPDATE SKIP LOCKED` and a finite lease.
2. Before embedding and before publication, it verifies Note existence, owner and version.
3. Obsolete/deleted jobs end without publishing data.
4. Transient Ollama failures use bounded exponential backoff; final failure sets Note `failed`.
5. A retry endpoint/action may return `failed` to `pending` without altering the persisted note.

## Transient Concepts (Not Persisted)

### SemanticQuery

| Field | Rules |
|-------|-------|
| `user_id` | Derived from authenticated session |
| `query` | Trimmed, 1–2,000 characters |
| `limit` | Default 5, range 1–10 |
| `embedding` | Generated with same pinned model as chunks |
| `minimum_similarity` | Configuration baseline 0.55; never returned as required UI data |

### RetrievalResult

Contains only authorized `note_id`, title, excerpt, chunk ordinal and internal similarity. Results are
deduplicated by note for public sources. Internal score is not exposed by the v1 contract.

### ChatDecision

Backend-validated result parsed from a `llama3:latest` completion requested in JSON format:

- `intent`: `answer` or `create_note`
- `title`: required only for an executable create intent
- `content`: required only for an executable create intent
- `clarification`: present when title/content or intent is ambiguous

The decision cannot contain or select `user_id`. The backend applies a strict schema; after at most one
repair attempt with the same model, invalid or ambiguous structures fail closed and request
clarification without persistence. No native tool-calling capability is assumed.

### ChatResponse

Contains `intent`, user-facing answer, authorized sources and optional created note. Conversation history
is not persisted in v1. The browser may display current-page messages until refresh.

## Row-Level Security Design

RLS applies to `notes`, `note_chunks` and `indexing_jobs`. At the start of each transaction, the
application sets a transaction-local current user UUID; policies use it in both `USING` and
`WITH CHECK`. The runtime role is non-owner and subject to `FORCE ROW LEVEL SECURITY`.

Privileged migrations use a separate role unavailable to request handling. Worker transactions set the
job owner's UUID before accessing note/chunk rows. Unit tests do not substitute for integration tests
that prove default-deny, ownership checks and runtime-role behavior.

## Transaction Boundaries

- **Register**: canonicalize, hash and insert User; unique conflict rolls back entirely.
- **Login**: verify password, create Session and rotate cookie; no partial session on failure.
- **Create/update Note**: mutate Note + upsert IndexingJob atomically.
- **Publish index**: validate version + replace NoteChunks + set Note ready + complete job atomically.
- **Delete Note**: delete aggregate and jobs atomically; response only after commit.
- **Create via chat**: validate structured decision, then invoke the ordinary create-note transaction.

## Retention and Sensitive Data

- Notes persist until explicit permanent deletion.
- Sessions persist only until operational cleanup after expiry/revocation.
- Sanitized job error codes may persist for diagnosis; raw model errors/prompts are not stored.
- Logs include request IDs, status, duration and safe entity IDs where necessary, but exclude password,
  cookie/session token, CSRF token, note body, retrieved chunks and full chat messages.
