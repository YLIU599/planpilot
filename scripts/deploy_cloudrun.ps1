param(
  [Parameter(Mandatory=$true)] [string] $ProjectId,
  [string] $Region = "us-central1",
  [string] $Repo = "planpilot-repo",
  [string] $Service = "planpilot",
  [string] $Model = "vertex_ai/gemini-2.5-flash"
)

$ErrorActionPreference = "Stop"

$Image = "$Region-docker.pkg.dev/$ProjectId/$Repo/$Service:latest"

gcloud config set project $ProjectId

gcloud services enable run.googleapis.com cloudbuild.googleapis.com artifactregistry.googleapis.com aiplatform.googleapis.com

# Create repo if missing.
gcloud artifacts repositories describe $Repo --location=$Region 2>$null
if ($LASTEXITCODE -ne 0) {
  gcloud artifacts repositories create $Repo --repository-format=docker --location=$Region --description="PlanPilot Docker repository"
}

gcloud builds submit --tag $Image

gcloud run deploy $Service `
  --image $Image `
  --region $Region `
  --platform managed `
  --allow-unauthenticated `
  --set-env-vars "VERTEX_PROJECT_ID=$ProjectId,VERTEX_LOCATION=$Region,MODEL=$Model,ENABLE_LLM_PARSING=false"

gcloud run services describe $Service --region $Region --format="value(status.url)"
