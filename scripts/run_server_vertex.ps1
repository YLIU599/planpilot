param(
  [Parameter(Mandatory=$true)] [string] $ProjectId,
  [string] $Location = "us-central1",
  [string] $Model = "vertex_ai/gemini-2.5-flash"
)

$ErrorActionPreference = "Stop"

$env:VERTEX_PROJECT_ID = $ProjectId
$env:VERTEX_LOCATION = $Location
$env:MODEL = $Model
$env:ENABLE_LLM_PARSING = "true"

uv run uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
