# Research: Gerenciamento de Anotações Pessoais com RAG

## Decision 1: Monólito modular em Python e FastAPI

**Decision**: Usar Python 3.13 e FastAPI para API, regras e worker; servir HTML/CSS/JavaScript estático
pela mesma aplicação.

**Rationale**: Python reduz a distância entre aplicação e ecossistema de IA. FastAPI fornece validação,
injeção de dependências e OpenAPI sem exigir uma arquitetura distribuída. O frontend é pequeno (acesso,
CRUD, busca e chat), então JavaScript sem framework evita outro build/runtime.

**Alternatives considered**:

- React/TypeScript: melhor para UI grande, mas acrescenta toolchain e abstrações sem necessidade atual.
- Django: integra mais recursos, porém o escopo não precisa de painel administrativo nem ORM acoplado.
- Microsserviços: rejeitados por custo operacional, testes distribuídos e ausência de escala justificadora.

**Sources**: [FastAPI Docker deployment](https://fastapi.tiangolo.com/deployment/docker/),
[Docker Python guide](https://docs.docker.com/guides/python/)

## Decision 2: PostgreSQL com pgvector como armazenamento único

**Decision**: Usar PostgreSQL 18.x e pgvector 0.8.x para usuários, sessões, notas, fila, chunks e vetores.

**Rationale**: Um banco preserva transações entre nota e job, suporta restrições e RLS e elimina a
sincronização com banco vetorial dedicado. Começar com distância cosseno exata, índice B-tree por
`user_id` e top-5; só introduzir HNSW após medição.

**Alternatives considered**:

- SQLite: mais leve, mas não oferece o mesmo isolamento em profundidade, concorrência do worker ou
  caminho vetorial integrado para este desenho.
- Banco vetorial separado: escalaria independentemente, mas duplica persistência e aumenta risco de
  divergência/exclusão incompleta.
- HNSW desde o início: melhora escala, porém troca recall por velocidade e filtros são aplicados após a
  varredura aproximada; desnecessário para até 100 mil chunks.

**Sources**: [pgvector](https://github.com/pgvector/pgvector),
[PostgreSQL row security](https://www.postgresql.org/docs/current/ddl-rowsecurity.html)

## Decision 3: Isolamento em duas camadas

**Decision**: Toda operação usa `user_id` derivado da sessão em filtros explícitos; RLS com `ENABLE` e
`FORCE ROW LEVEL SECURITY` fornece defesa adicional. A role runtime não é proprietária, superusuária nem
possui `BYPASSRLS`.

**Rationale**: O requisito de isolamento é não negociável. Filtros explícitos tornam a intenção legível;
RLS contém falhas de omissão. Consultas por ID combinam `(id, user_id)` e retornam o mesmo 404 para nota
ausente ou alheia. Recuperação semântica aplica o dono antes da ordenação.

**Alternatives considered**:

- Somente filtros da aplicação: mais simples, mas uma omissão pode vazar dados.
- Um schema/banco por usuário: isolamento forte, porém inviável operacionalmente para o escopo.

**Sources**: [PostgreSQL RLS](https://www.postgresql.org/docs/current/ddl-rowsecurity.html),
[OWASP Broken Object Level Authorization](https://owasp.org/API-Security/editions/2023/en/0xa1-broken-object-level-authorization/)

## Decision 4: Sessão opaca e senha com Argon2id

**Decision**: Normalizar nome de usuário com trim e casefold, preservar o nome exibido e impor unicidade
no canônico. Hash de senha Argon2id com salt individual e parâmetros calibrados (mínimo inicial OWASP:
19 MiB, 2 iterações, paralelismo 1). Sessões usam token aleatório; apenas seu hash é persistido. Cookie
`HttpOnly`, `SameSite=Strict`, `Path=/`, sem `Domain`, `Secure` quando HTTPS; mutações exigem CSRF e
validação de origem. Logout revoga a sessão.

**Rationale**: Sessão server-side é simples de revogar e não expõe token ao JavaScript. Argon2id é
resistente a ataques com memória especializada. Erros de login permanecem genéricos.

**Alternatives considered**:

- JWT no armazenamento do navegador: evita tabela, mas revogação é complexa e eleva impacto de XSS.
- Basic Auth: reenvia credenciais e oferece experiência inadequada.
- Provedor externo: viola a preferência local e não é requisito.

**Sources**: [OWASP password storage](https://cheatsheetseries.owasp.org/cheatsheets/Password_Storage_Cheat_Sheet.html),
[OWASP session management](https://cheatsheetseries.owasp.org/cheatsheets/Session_Management_Cheat_Sheet.html),
[OWASP CSRF prevention](https://cheatsheetseries.owasp.org/cheatsheets/Cross-Site_Request_Forgery_Prevention_Cheat_Sheet.html)

## Decision 5: Fila transacional no PostgreSQL

**Decision**: Criar/atualizar nota e inserir `indexing_job` na mesma transação. Um worker da mesma imagem
reivindica jobs por `FOR UPDATE SKIP LOCKED`, usa tentativas com backoff e publica chunks somente se
`note_version` continuar atual. Jobs obsoletos são descartados; exclusão remove nota, chunks e jobs em
uma transação.

**Rationale**: Cumpre persistência imediata e indexação assíncrona durável sem Redis/Celery. O estado
`pending|processing|ready|failed` permite informar preparação e testar o SLA de 30 segundos.

**Alternatives considered**:

- Tarefa em memória: simples, mas perde trabalho ao reiniciar.
- Indexação síncrona: bloqueia salvamento e acopla disponibilidade do Ollama ao CRUD.
- Broker dedicado: robusto em escala, mas é infraestrutura não demonstrada.

**Source**: [PostgreSQL SELECT / SKIP LOCKED](https://www.postgresql.org/docs/current/sql-select.html)

## Decision 6: Embeddings multilíngues locais

**Decision**: Usar `embeddinggemma:300m` via Ollama, fixado por digest, gerando vetores de 768 dimensões.
O texto é `título + duas quebras + conteúdo`. Notas curtas formam um chunk; textos maiores são divididos
por parágrafos/sentenças em alvo de 350 tokens com overlap de 50.

**Rationale**: O modelo é compacto e multilíngue, adequado ao português e ao perfil local. O mesmo
modelo/formatação é usado na indexação e consulta. Troca de modelo exige reindexação completa.

**Alternatives considered**:

- `bge-m3`: contexto e recursos maiores, mas mais consumo; será considerado somente se a avaliação em
  português demonstrar ganho relevante.
- Embeddings externos: rejeitados pela autonomia local e privacidade.
- Um vetor por nota sem chunking: perde foco em textos longos.

**Sources**: [EmbeddingGemma model card](https://ollama.com/library/embeddinggemma),
[Ollama embeddings API](https://docs.ollama.com/api/embed),
[BGE-M3 model card](https://huggingface.co/BAAI/bge-m3)

## Decision 7: Recuperação exata e limiar calibrável

**Decision**: Busca cosseno exata pré-filtrada por usuário, top-5 e limiar inicial configurável de
similaridade 0,55. Calibrar o limiar com conjunto fixo em português; medir Recall@5, contexto indevido e
perguntas sem evidência. No modo RAG, se nenhum chunk passar, não chamar geração fundamentada e retornar
fontes vazias com indicação de insuficiência. Essa ausência não decide se uma mensagem é conversa geral.

**Rationale**: Scores não têm interpretação universal. Configuração versionada permite ajuste sem
codificar uma suposição como regra de domínio. Busca exata maximiza recall no envelope inicial.

**Alternatives considered**:

- Sem limiar: força contexto irrelevante e alucinação.
- Limiar fixo não calibrado: não transfere entre modelos/corpus.
- Busca híbrida lexical: pode ser adicionada se a avaliação demonstrar falha, mas não é necessária já.

**Source**: [pgvector distance and indexing](https://github.com/pgvector/pgvector)

## Decision 8: Ollama e Llama 3 para geração local (human override)

**Original SDD decision**: O planejamento escolheu inicialmente `qwen3:4b` como baseline e
`qwen3:8b` como perfil opcional, com base em tamanho, suporte multilíngue e capacidades de saída
estruturada/tool calling.

**Superseding decision**: Por intervenção humana em 2026-08-17, substituir a escolha original pelo
único modelo generativo `llama3:latest`, executado via Ollama. A tag deve resolver para o ID local
observado `365c0bd3c000`: arquitetura llama, 8.0B parâmetros (8.03B no catálogo), contexto 8192, Q4_0 e
capacidade observada `completion`. O startup/model-init deve verificar tag e ID, pois `latest` é mutável,
e interromper a aceitação se não houver correspondência. `embeddinggemma:300m` não é alterado.

**Rationale**: A escolha é uma restrição de controle experimental: usar o mesmo modelo generativo da
implementação de referência torna os resultados comparáveis e isola o modelo como variável controlada.
Ollama preserva execução local, persistência de modelo e caminhos CPU/NVIDIA/AMD.

**Compatibility impact**: O catálogo observado de `llama3:latest` declara completion, não tool calling.
O plano não atribui suporte nativo a ferramentas. O endpoint de completion/chat do Ollama será chamado
com `format: json` ou JSON Schema, temperatura 0 e instrução explícita; o backend valida a resposta com
schema estrito, permite no máximo uma tentativa de reparo pelo mesmo modelo e falha fechado. Saída
inválida, intenção mista ou campos ausentes resultam em esclarecimento sem persistência. Structured
output é uma restrição oferecida pelo runtime Ollama, mas sua confiabilidade com esta tag deve ser
comprovada pela suíte de avaliação; não é tratada como capacidade equivalente de tool calling.

**Alternatives considered**:

- Manter `qwen3:4b`: escolha técnica original, rejeitada para não quebrar a comparabilidade experimental.
- Adicionar segundo LLM para classificação: rejeitado porque contornaria a variável experimental e
  aumentaria a infraestrutura.
- Tool calling nativo: não assumido porque a tag observada não declara essa capacidade.
- API externa: pode ser adaptador futuro, mas não participa do caminho principal.
- Ollama somente no host: facilita GPU no Windows, porém não é o caminho reproduzível obrigatório.

**Sources**: [Llama 3 library](https://ollama.com/library/llama3),
[Llama 3 tags](https://ollama.com/library/llama3/tags),
[Ollama Docker](https://docs.ollama.com/docker),
[Ollama structured outputs](https://docs.ollama.com/capabilities/structured-outputs)

## Decision 9: RAG fundamentado e fontes controladas pelo backend

**Decision**: Delimitar chunks autorizados com IDs opacos; instruir o modelo a responder somente com o
contexto, declarar insuficiência e ignorar instruções contidas nas notas. O modelo cita IDs fornecidos,
mas o backend valida/deduplica e monta fontes (`note_id`, título, trecho) apenas a partir dos chunks
enviados.

**Rationale**: A saída textual do modelo não é autoridade de acesso. A validação impede fontes
inventadas e mantém rastreabilidade. Conteúdo de notas é dado não confiável, mitigando prompt injection.

**Alternatives considered**:

- Confiar nas citações do modelo: simples, mas permite IDs inventados.
- Responder com conhecimento geral dentro de uma consulta às notas: viola o grounding desse modo.
- Framework RAG: rejeitado inicialmente; poucas funções explícitas são mais auditáveis e testáveis.

## Decision 10: Criação por intenção estruturada

**Decision original**: Solicitar ao `llama3:latest`, como completion e sem tools, JSON com
`intent=answer|create_note`, `title` e `content`, usando a restrição de formato do runtime Ollama. O
backend valida a estrutura, deriva o dono da sessão e persiste por meio do mesmo serviço de CRUD. Uma
saída inválida permite no máximo uma tentativa de reparo pelo mesmo modelo; nova falha, campos ausentes
ou intenção mista produzem pergunta de esclarecimento sem escrita.

**Revisão de 2026-08-19**: A estrutura passa a distinguir
`rag|general_chat|create_note|clarification`. Campos de título e conteúdo e o fluxo de persistência de
`create_note` permanecem inalterados. `clarification` cobre ambiguidade real e múltiplas intenções e não
autoriza resposta substantiva nem escrita.

**Rationale**: Separa interpretação probabilística da autorização determinística sem depender de tool
calling não declarado pelo modelo. O modelo nunca recebe capacidade de SQL nem escolhe `user_id`.

**Alternatives considered**:

- Regex/comandos rígidos: previsível, mas não atende linguagem natural ampla.
- Agente/tool calling: não é capacidade declarada de `llama3:latest` e ampliaria a superfície de risco.

**Sources**: [Ollama structured outputs](https://docs.ollama.com/capabilities/structured-outputs),
[Llama 3 model entry](https://ollama.com/library/llama3%3A8b-instruct-q4_0)

## Decision 11: REST JSON e respostas não-streaming

**Decision**: Expor `/api/v1` conforme `contracts/openapi.yaml`; UI e API compartilham origem. O chat
retorna uma resposta completa na v1. Erros usam envelope uniforme e `request_id`; dados privados usam
`Cache-Control: no-store`.

**Rationale**: Contrato explícito habilita testes e cliente simples. Streaming adicionaria reconexão,
cancelamento e contrato incremental sem requisito de latência percebida.

**Alternatives considered**:

- SSE/WebSocket: reconsiderar após medição de UX.
- GraphQL: flexibilidade desnecessária para recursos pequenos e estáveis.

**Source**: [OpenAPI 3.1 specification](https://spec.openapis.org/oas/v3.1.1.html)

## Decision 12: Testes em camadas e avaliação de RAG

**Decision**: pytest para unidades/integração/contrato/segurança; PostgreSQL/pgvector real nas integrações;
Ollama falso determinístico na suíte padrão e testes reais marcados; Playwright para E2E. Matriz
anônimo/dono/outro usuário cobre cada operação. Dataset em português mede os SC-004 a SC-008 e o
conjunto conversacional adicional mede SC-012 e as decisões de clarification de 2026-08-19.

**Rationale**: Testes determinísticos protegem regras; avaliação separada reconhece variabilidade e
custo do modelo. Nenhuma funcionalidade termina com critérios relevantes falhando.

**Alternatives considered**:

- Mockar o banco: não testa RLS, vetores nem transações.
- Exigir LLM real em toda suíte: lento e instável.
- Avaliação manual apenas: não detecta regressões repetíveis.

**Sources**: [FastAPI testing](https://fastapi.tiangolo.com/tutorial/testing/),
[Playwright Python](https://playwright.dev/python/docs/intro),
[OWASP authorization testing](https://cheatsheetseries.owasp.org/cheatsheets/Authorization_Testing_Automation_Cheat_Sheet.html)

## Decision 13: Docker Compose com quatro serviços

**Decision**: `web`, `index-worker`, `db` e `ollama`; web/worker compartilham imagem. Volumes nomeados,
healthchecks, migração one-shot e imagens/modelos fixados. Perfil CPU obrigatório; GPU opcional.

**Rationale**: É o menor conjunto que separa responsabilidades de execução e preserva dados/modelos.
Compose documenta dependências e permite reproduzir o fluxo principal.

**Alternatives considered**:

- Embutir todos os processos em um container: lifecycle e falhas ficam acoplados.
- Kubernetes: fora de escala.
- Banco/modelo somente no host: reduz reprodutibilidade.

**Sources**: [Docker Compose startup order](https://docs.docker.com/compose/how-tos/startup-order/),
[Compose volumes](https://docs.docker.com/reference/compose-file/volumes/),
[Ollama Docker](https://docs.ollama.com/docker)

## Decision 14: Roteamento conversacional de três modos (revisão pós-implementação)

**Historical decision**: A primeira implementação SDD tratava toda mensagem não classificada como
`create_note` como `answer`, executava retrieval e recusava quando o corpus era insuficiente. Essa
decisão de RAG restritivo global foi coerente com a Especificação-Base então disponível.

**Superseding decision (2026-08-19)**: Para restaurar uma capacidade da aplicação de referência omitida
da Especificação-Base, classificar e validar a intenção expressa antes de qualquer retrieval como
`rag`, `general_chat`, `create_note` ou `clarification`. `rag` executa recuperação autorizada e nunca
faz fallback geral; `general_chat` chama diretamente o mesmo `llama3:latest` sem contexto nem fontes;
`clarification` solicita uma única intenção sem responder ou persistir; `create_note` preserva o fluxo
existente. O contrato expõe o discriminador no campo `intent`, e a UI deriva dele “Resposta geral” ou
“Baseada nas suas anotações”.

**Rationale**: A ausência de resultados é evidência sobre suficiência do corpus, não sobre a intenção
da mensagem. Usá-la como roteador confundiria “O que é Docker?” com “O que eu anotei sobre Docker?” e
permitiria fallback silencioso indevido. Decidir o modo antes da busca mantém as fronteiras testáveis e
preserva o grounding de consultas pessoais.

**Alternatives considered**:

- Decidir pelo resultado do retrieval: rejeitado porque similaridade ou ausência de notas não expressa
  a intenção do usuário.
- Fazer retrieval para toda pergunta e usar contexto quando disponível: rejeitado porque converteria
  perguntas gerais em RAG apenas pela existência de nota semelhante.
- Fazer fallback geral quando RAG não encontra contexto: rejeitado por violar FR-014.
- Adicionar segundo classificador/LLM ou agente com tool calling: rejeitado por aumentar arquitetura e
  alterar a variável experimental; o mesmo `llama3:latest` e a validação backend são suficientes.
- Criar endpoint separado para conversa geral: rejeitado porque o endpoint atual já representa a
  interface conversacional e um discriminador explícito é a menor mudança contratual.

**Scope note**: Esta decisão supersedes somente o roteamento globalmente RAG restritivo. Recuperação,
RLS, validação de fontes, criação de notas, SC-008, modelo generativo, API não-streaming e topologia de
implantação permanecem preservados. A inconsistência manual de criação continua sendo ocorrência
experimental separada.
