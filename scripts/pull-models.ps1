$ErrorActionPreference = "Stop"
docker compose up -d ollama
docker compose run --rm model-init
docker compose run --rm model-init
