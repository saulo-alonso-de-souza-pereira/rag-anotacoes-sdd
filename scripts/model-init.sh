#!/bin/sh
set -eu
ollama list | awk '{print $1}' | grep -qx 'embeddinggemma:300m' || ollama pull embeddinggemma:300m
ollama list | awk '{print $1}' | grep -qx 'llama3:latest' || ollama pull llama3:latest
embedding_identity="$(ollama list | awk '$1 == "embeddinggemma:300m" {print $2}')"
generation_identity="$(ollama list | awk '$1 == "llama3:latest" {print $2}')"
test "$embedding_identity" = "$NOTES_EMBEDDING_MODEL_DIGEST"
test "$generation_identity" = "$NOTES_GENERATION_MODEL_ID"
