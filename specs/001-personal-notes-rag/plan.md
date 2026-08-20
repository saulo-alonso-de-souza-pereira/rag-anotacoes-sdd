# Implementation Plan: Gerenciamento de Anotações Pessoais com RAG

**Branch**: `001-personal-notes-rag` | **Date**: 2026-08-17 | **Revised**: 2026-08-19 | **Spec**: [spec.md](spec.md)

**Input**: Feature specification from `/specs/001-personal-notes-rag/spec.md`

## Summary

Implementar uma aplicação web local para cadastro e autenticação, CRUD isolado de anotações,
recuperação semântica e chatbot com criação de notas, consultas RAG fundamentadas e conversa geral. A solução será
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

**Constraints**: Fluxo principal sem API externa de LLM; consultas RAG usam exclusivamente o corpus de
anotações autorizado, enquanto conversa geral usa o mesmo modelo local sem fontes; isolamento por
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
| Testabilidade | Contrato OpenAPI, testes unitários, integração, segurança, E2E, eval RAG e matriz dos três modos | PASS | PASS |
| Rastreabilidade | Histórico preservado; revisão ligada a FR-011/013/014/015/022/023 e SC-012 em `research.md` | PASS | PASS |
| Qualidade e manutenibilidade | Módulos por responsabilidade, erros uniformes, dependências mínimas e lockfile | PASS | PASS |
| Separação entre requisitos e implementação | A specification permaneceu tecnologicamente agnóstica; escolhas estão neste plano | PASS | PASS |
| Governança | Nenhuma violação; gates repetidos após modelo, contratos e quickstart | PASS | PASS |

### Gate pós-design

O design mantém uma única aplicação implantável e introduz somente dois processos da mesma imagem.
O worker separado é justificado pelo requisito de persistir imediatamente e indexar em até 30 segundos.
PostgreSQL/pgvector elimina um banco vetorial separado; a tabela de jobs elimina um broker dedicado.
Na revisão de 2026-08-19, o novo modo reutiliza o endpoint, o adaptador Ollama, o único modelo generativo
e a UI existentes; acrescenta apenas um discriminador e ramificações testáveis. O isolamento do RAG e
a validação backend de fontes permanecem intactos. Não há violações da constitution nem
`NEEDS CLARIFICATION` remanescentes.

## Architecture

### Revisão incremental pós-implementação (2026-08-19)

A primeira implementação roteava `create_note` ou `answer`, sendo `answer` sempre RAG restritivo. Esta
revisão corrige uma omissão funcional da Especificação-Base identificada após implementação e validação,
restaurando a equivalência com a aplicação de referência. Não é melhoria opcional pós-entrega. O desenho
existente é preservado e recebe somente um roteamento explícito anterior ao retrieval:

```text
mensagem autenticada
       |
       v
decisão validada: create_note | rag | general_chat | clarification
       |                 |              |                 |
       |                 |              |                 +--> pedir uma intenção; sem escrita/geração
       |                 |              +--> llama3:latest sem retrieval e sem fontes
       |                 +--> retrieval autorizado --> grounded ou insuficiência, nunca fallback geral
       +--> fluxo de criação existente
```

A intenção expressa na mensagem determina o ramo. Retrieval não é executado para decidir intenção e a
existência, ausência ou similaridade de notas não pode reclassificar `general_chat` como `rag`. Mensagens
realmente ambíguas ou com múltiplas intenções produzem `clarification` sem execução parcial.

| Requisito revisado | Decisão de planejamento |
|--------------------|-------------------------|
| FR-011, FR-013, FR-014 | Retrieval existe somente no ramo `rag`; contexto insuficiente permanece nesse ramo |
| FR-015 | Fontes continuam validadas no backend e o modo grounded recebe indicador próprio |
| FR-022 | Decisão estruturada distingue três modos e esclarecimento antes de qualquer efeito |
| FR-023 | `general_chat` não recebe contexto de notas, retorna `sources=[]` e indicador próprio |
| SC-012 | Testes de contrato, unidade e E2E cobrem roteamento, fontes e indicadores |

```text
Browser (same-origin)
       |
       v
Web application (FastAPI + static UI)
  |         |                 |
  |         |                 +--> Ollama: completion para intenção + geração RAG ou geral
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
6. **Roteamento explícito de três modos (supersedes o roteamento globalmente RAG restritivo)**: ampliar
   a decisão estruturada de `answer|create_note` para `rag|general_chat|create_note|clarification`, sem
   novo modelo ou tool calling. O backend valida a decisão antes de qualquer retrieval. `rag` mantém
   top-5, limiar configurável, resposta somente com contexto, insuficiência sem fallback e fontes
   reconstruídas/validadas no backend. `general_chat` chama diretamente o mesmo `llama3:latest`, sem
   contexto nem fontes de anotações. `clarification` não gera resposta substantiva nem persiste nota.
   A UI mapeia `general_chat` para “Resposta geral” e `rag` respondido com notas para “Baseada nas suas
   anotações”. O `needs_clarification` existente é preservado no contrato por compatibilidade.
7. **Sem histórico conversacional persistente na v1**: cada mensagem é independente; reduz dados e
   escopo porque a specification não exige memória de conversa.

O comportamento de criação especificado em FR-016/FR-017 e SC-008 permanece inalterado. A inconsistência
manual observada com criação via `llama3:latest` continua registrada como ocorrência experimental
separada e não é corrigida nem acomodada por esta revisão.

## Testing Strategy

- **Unitários**: normalização, validações, hashes, chunking, estados, roteamento estruturado dos quatro
  resultados, montagem separada de prompts RAG/geral, seleção/validação de fontes e mapeamento de erros.
- **Contrato**: validação do OpenAPI, schemas, códigos, cookies e envelopes de erro.
- **Integração**: PostgreSQL/pgvector real, migrações, unicidade concorrente, transações, RLS, fila,
  versionamento e exclusão atômica; adaptador Ollama falso determinístico na suíte padrão.
- **Segurança**: matriz anônimo/dono/outro usuário para toda operação; CSRF, expiração/revogação,
  enumeração, logs e prompt injection.
- **E2E**: cadastro até RAG, conversa geral e criação via chat, indicadores visuais, persistência após
  restart e falha previsível do Ollama.
- **Avaliação conversacional**: corpus fixo em português cobre RAG explícito com e sem contexto,
  conversa geral com e sem nota semelhante, ausência de fontes no modo geral, fontes autorizadas no
  modo RAG, ambiguidade e múltiplas intenções. Testes reais do modelo permanecem separados por hardware.

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
