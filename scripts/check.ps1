$ErrorActionPreference = "Stop"
$PSNativeCommandUseErrorActionPreference = $true
$root = Split-Path -Parent $PSScriptRoot

function Invoke-Checked {
    & $args[0] $args[1..($args.Count - 1)]
    if ($LASTEXITCODE -ne 0) {
        throw "Command failed with exit code ${LASTEXITCODE}: $($args -join ' ')"
    }
}

Push-Location (Join-Path $root "app")
try {
    Invoke-Checked uv sync --frozen
    Invoke-Checked uv run --frozen ruff format --check src tests migrations
    Invoke-Checked uv run --frozen ruff check src tests migrations
    Invoke-Checked uv run --frozen alembic heads
    Invoke-Checked uv run --frozen pytest -q
    Invoke-Checked uv run --frozen pytest -q -m "e2e and not compose" --no-cov --browser chromium
    if ($env:NOTES_RUN_LIVE_MODEL -eq "1") {
        Invoke-Checked docker compose run --rm --no-deps web pytest -q -m live_model tests/rag_eval/test_retrieval_quality.py --no-cov
        Invoke-Checked uv run --frozen pytest -q -o addopts= tests/performance/test_local_targets.py -s
    }
    if ($env:NOTES_RUN_COMPOSE_ACCEPTANCE -eq "1") {
        Invoke-Checked uv run --frozen pytest -q -o addopts= tests/e2e/test_compose_quickstart.py -s
    }
    if ($env:NOTES_RUN_OFFLINE_ACCEPTANCE -eq "1") {
        Invoke-Checked uv run --frozen pytest -q -o addopts= tests/e2e/test_offline_flow.py -s
    }
}
finally {
    Pop-Location
}
