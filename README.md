# Personal Notes RAG

Aplicativo local de anotações pessoais com busca semântica, respostas fundamentadas e criação
conversacional. API, worker, PostgreSQL/pgvector e Ollama executam localmente; nenhuma API externa de
LLM participa do fluxo principal.

## Perfil de referência

- Windows 11 com Docker Desktop/WSL2 ou Linux com Docker Engine e Compose v2;
- CPU x86-64 com 4 núcleos, 8 GB de RAM livres e cerca de 8 GB de disco;
- PowerShell 7+ para os scripts `.ps1`;
- rede somente para o primeiro build e download das imagens/modelos.

GPU não é necessária para a aceitação. NVIDIA pode ser habilitada com
`docker compose -f compose.yaml -f compose.gpu.yaml --profile gpu up`; o caminho CPU continua sendo a
referência obrigatória.

## Configuração e primeira inicialização

```powershell
Copy-Item .env.example .env
```

No `.env`, substitua todos os `CHANGE_ME`, use as mesmas senhas nos URLs correspondentes e registre o
ID observado de `embeddinggemma:300m`. O arquivo `.env` é ignorado pelo Git e pelo contexto Docker.

```powershell
docker compose build
docker compose up -d db ollama
./scripts/pull-models.ps1
./scripts/migrate.ps1
docker compose up -d web index-worker
docker compose ps
```

O primeiro download não integra a meta de inicialização e deve ser cronometrado separadamente. O
`model-init` é idempotente e interrompe o fluxo se `llama3:latest` não resolver para
`365c0bd3c000` ou se o ID do embedding divergir do valor configurado. Depois dos downloads, abra
`http://localhost:8000`.

## Verificação

```powershell
./scripts/check.ps1
```

Os cenários manuais completos, incluindo isolamento entre Alice/Bob, restart, modo offline e medições,
estão em `specs/001-personal-notes-rag/quickstart.md`.

## Parada segura

```powershell
docker compose down
```

Esse comando preserva `postgres-data` e `ollama-models`. Não use `--volumes` na operação normal:
essa opção remove permanentemente os dados e modelos locais.
