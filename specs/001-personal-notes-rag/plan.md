# Implementation Plan: Gerenciamento de Anotações Pessoais com RAG

**Branch**: `001-personal-notes-rag` | **Date**: 2026-08-17 | **Spec**: [spec.md](spec.md)

**Input**: Feature specification from `/specs/001-personal-notes-rag/spec.md`

## Summary

Implementar uma aplicação web local para cadastro e autenticação, CRUD isolado de anotações,
recuperação semântica e chatbot RAG com fontes e criação de notas em linguagem natural. A solução será
um monólito modular em Python/FastAPI que serve API e frontend estático, acompanhado por um processo
worker da mesma imagem. PostgreSQL com pgvector manterá dados relacionais, vetores e fila transacional;
Ollama executará localmente embeddings e geração. Docker Compose fornecerá o caminho reproduzível.

## Technical Context

**Language/Version**: Python 3.13.x no backend/worker; HTML5, CSS3 e JavaScript ES2023 sem framework no
frontend

**Primary Dependencies**: FastAPI 0.137.x, Pydantic 2.x, SQLAlchemy 2.0.x, Alembic 1.18.x, psycopg 3.x,
pgvector-python 0.4.x, httpx 0.28.x, pwdlib com Argon2; dependências bloqueadas por lockfile

**Storage**: PostgreSQL 18.x com pgvector 0.8.x; volumes persistentes para banco e modelos Ollama

**Testing**: pytest 9.x, pytest-asyncio, HTTPX/ASGI transport, testcontainers ou Compose para integração,
pytest-playwright para E2E e suíte de avaliação RAG em português

**Target Platform**: Docker Desktop em Windows/WSL2 e Docker Engine Linux; CPU x86-64 como baseline,
aceleração GPU opcional

**Project Type**: Aplicação web monolítica modular com API JSON, frontend estático e worker assíncrono

**Performance Goals**: CRUD e listagem p95 abaixo de 500 ms em carga local de referência; busca
semântica p95 abaixo de 2 s; 95% das notas prontas para recuperação em até 30 s; pelo menos 90% das
respostas completas do chatbot apresentadas em até 60 s no perfil CPU documentado

**Constraints**: Fluxo principal sem API externa de LLM; corpus somente de anotações; isolamento por
usuário em aplicação e banco; exclusão permanente; fontes verificadas pelo backend; inicialização em
ambiente limpo em até 15 minutos após modelos e imagens estarem disponíveis

**Scale/Scope**: Instalação local de instância única; até 100 usuários, 10.000 anotações totais,
100.000 chunks e 10 sessões ativas simultâneas como envelope inicial de validação

## Constitution Check

*GATE: aprovado antes da pesquisa e reavaliado após o design da Fase 1.*

| Princípio | Evidência no plano | Estado inicial | Pós-design |
|-----------|--------------------|----------------|------------|
| Simplicidade e clareza | Monólito modular, frontend sem framework, um banco e fila no próprio banco | PASS | PASS |
| Segurança e privacidade | Sessão opaca, Argon2id, filtros por dono, RLS, CSRF e testes de acesso cruzado | PASS | PASS |
| Testabilidade | Contrato OpenAPI, camadas substituíveis, testes unitários, integração, segurança, E2E e eval RAG | PASS | PASS |
| Rastreabilidade | Decisões e alternativas registradas em `research.md`; contratos ligados a FRs | PASS | PASS |
| Qualidade e manutenibilidade | Módulos por responsabilidade, erros uniformes, dependências mínimas e lockfile | PASS | PASS |
| Separação entre requisitos e implementação | A specification permaneceu tecnologicamente agnóstica; escolhas estão neste plano | PASS | PASS |
| Governança | Nenhuma violação; gates repetidos após modelo, contratos e quickstart | PASS | PASS |

### Gate pós-design

O design mantém uma única aplicação implantável e introduz somente dois processos da mesma imagem.
O worker separado é justificado pelo requisito de persistir imediatamente e indexar em até 30 segundos.
PostgreSQL/pgvector elimina um banco vetorial separado; a tabela de jobs elimina um broker dedicado.
Não há violações da constitution nem `NEEDS CLARIFICATION` remanescentes.

## Architecture

```text
Browser (same-origin)
       |
       v
Web application (FastAPI + static UI)
  |         |                 |
  |         |                 +--> Ollama: completion para intenção + geração fundamentada
  |         +--> PostgreSQL/pgvector: CRUD, sessions, exact semantic search, RLS
  +--> indexing_jobs (same transaction as note mutation)
                    |
                    v
            Index worker (same app image)
                    |
                    +--> Ollama embeddings
                    +--> PostgreSQL/pgvector chunks and status
```

- A API deriva `user_id` exclusivamente da sessão; corpos e parâmetros nunca escolhem proprietário.
- CRUD e enfileiramento da indexação compartilham uma transação. O worker publica embeddings somente se
  a versão da nota ainda for atual.
- A recuperação filtra `user_id` antes de ordenar por distância cosseno e começa com busca exata.
- O backend monta contexto, valida IDs de citação e é o único componente autorizado a persistir notas.
- O navegador não acessa Ollama nem PostgreSQL diretamente.

## Project Structure

### Documentation (this feature)

```text
specs/001-personal-notes-rag/
├── plan.md
├── research.md
├── data-model.md
├── quickstart.md
├── contracts/
│   └── openapi.yaml
└── tasks.md
```

### Source Code (repository root)

```text
app/
├── pyproject.toml
├── uv.lock
├── alembic.ini
├── migrations/
├── src/notes_rag/
│   ├── main.py
│   ├── config.py
│   ├── api/
│   │   ├── auth.py
│   │   ├── notes.py
│   │   ├── search.py
│   │   ├── chat.py
│   │   └── errors.py
│   ├── domain/
│   │   ├── users.py
│   │   ├── notes.py
│   │   └── chat.py
│   ├── services/
│   │   ├── authentication.py
│   │   ├── indexing.py
│   │   ├── retrieval.py
│   │   ├── rag.py
│   │   └── intent.py
│   ├── persistence/
│   │   ├── models.py
│   │   ├── repositories.py
│   │   └── rls.py
│   ├── llm/
│   │   └── ollama.py
│   ├── worker.py
│   └── web/
│       ├── index.html
│       ├── styles.css
│       └── app.js
└── tests/
    ├── unit/
    ├── contract/
    ├── integration/
    ├── security/
    ├── e2e/
    └── rag_eval/

compose.yaml
Dockerfile
.env.example
scripts/
└── pull-models.ps1
```

**Structure Decision**: Uma única base Python concentra regras, API e worker; `api`, `domain`,
`services`, `persistence` e `llm` são limites simples e testáveis. O frontend estático evita um segundo
toolchain, mas permanece isolado em `web`. Web e worker usam a mesma imagem e configuração.

## Key Technical Decisions

1. **API e UI same-origin**: reduz CORS e exposição de cookies; OpenAPI 3.1 é o contrato verificável.
2. **Sessão opaca em cookie**: revogação imediata e nenhum token acessível ao JavaScript; estado de
   sessão no banco é aceitável para instância única.
3. **PostgreSQL + pgvector**: transações, RLS e vetores no mesmo armazenamento evitam sincronização
   entre bancos. Busca exata é suficiente no envelope inicial e preserva recall após filtro por usuário.
4. **Outbox no banco**: `indexing_jobs` durável com `FOR UPDATE SKIP LOCKED`; sem Redis/Celery.
5. **Ollama local**: `embeddinggemma:300m` permanece responsável por embeddings multilíngues;
   `llama3:latest` (`365c0bd3c000`, arquitetura llama, 8.0B, contexto 8192, Q4_0) é o único modelo
   generativo do fluxo principal por controle experimental. A inicialização verifica que a tag resolve
   para o ID observado e falha de modo explícito em caso de divergência.
6. **RAG restritivo**: top-5, limiar inicial configurável, resposta somente com contexto, recusa quando
   insuficiente e fontes reconstruídas/validadas no backend. Como `llama3:latest` declara somente
   capacidade de completion, o desenho não depende de tool calling: a intenção é solicitada em JSON
   pelo runtime Ollama, validada no backend e rejeitada com segurança quando inválida ou ambígua.
7. **Sem histórico conversacional persistente na v1**: cada mensagem é independente; reduz dados e
   escopo porque a specification não exige memória de conversa.

## Testing Strategy

- **Unitários**: normalização, validações, hashes, chunking, estados, intenção estruturada, montagem de
  prompt, seleção/validação de fontes e mapeamento de erros.
- **Contrato**: validação do OpenAPI, schemas, códigos, cookies e envelopes de erro.
- **Integração**: PostgreSQL/pgvector real, migrações, unicidade concorrente, transações, RLS, fila,
  versionamento e exclusão atômica; adaptador Ollama falso determinístico na suíte padrão.
- **Segurança**: matriz anônimo/dono/outro usuário para toda operação; CSRF, expiração/revogação,
  enumeração, logs e prompt injection.
- **E2E**: cadastro até RAG e criação via chat, persistência após restart e falha previsível do Ollama.
- **Avaliação RAG**: corpus fixo em português, Recall@5, contexto indevido, groundedness, fontes e
  intenção; testes reais do modelo separados e marcados por hardware.

## Containerization

Docker Compose executará `web`, `index-worker`, `db` e `ollama`. Web e worker derivam do mesmo
Dockerfile multi-stage; PostgreSQL e modelos usam volumes nomeados. Healthchecks controlam a ordem de
prontidão; migrações rodam como comando one-shot idempotente antes da aplicação. O perfil CPU é o
caminho obrigatório de aceitação; perfis GPU são opcionais. Segredos ficam em ambiente/arquivo local
ignorado, nunca na imagem ou no repositório. O primeiro download de imagens/modelos exige rede; depois,
o fluxo principal não depende de APIs externas.

## Complexity Tracking

Nenhuma violação constitucional requer exceção. O processo worker adicional é parte da mesma aplicação
e está diretamente justificado pelo SLA de indexação; os componentes mais complexos (broker dedicado,
banco vetorial separado, frontend framework, microsserviços e índice aproximado) foram rejeitados.
