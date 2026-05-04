# Cloud Run Deployment Guide

This deployment flow matches the FastAPI + Docker + Cloud Run pattern used in earlier projects.

## 1. Set project

```powershell
gcloud auth login
gcloud config set project YOUR_PROJECT_ID
```

Optional for local Vertex testing:

```powershell
gcloud auth application-default login
```

## 2. Enable services

```powershell
gcloud services enable run.googleapis.com cloudbuild.googleapis.com artifactregistry.googleapis.com aiplatform.googleapis.com
```

## 3. Create Artifact Registry repo

```powershell
gcloud artifacts repositories create planpilot-repo `
  --repository-format=docker `
  --location=us-central1 `
  --description="PlanPilot Docker repository"
```

If it already exists, skip this step.

## 4. Build image

```powershell
gcloud builds submit --tag "us-central1-docker.pkg.dev/YOUR_PROJECT_ID/planpilot-repo/planpilot:latest"
```

## 5. Deploy to Cloud Run

Initial deployment without LLM parsing:

```powershell
gcloud run deploy planpilot `
  --image "us-central1-docker.pkg.dev/YOUR_PROJECT_ID/planpilot-repo/planpilot:latest" `
  --region us-central1 `
  --platform managed `
  --allow-unauthenticated `
  --set-env-vars VERTEX_PROJECT_ID=YOUR_PROJECT_ID,VERTEX_LOCATION=us-central1,MODEL=vertex_ai/gemini-2.5-flash,ENABLE_LLM_PARSING=false
```

After confirming Cloud Run service account has Vertex AI access, enable LLM parsing:

```powershell
gcloud run services update planpilot `
  --region us-central1 `
  --set-env-vars VERTEX_PROJECT_ID=YOUR_PROJECT_ID,VERTEX_LOCATION=us-central1,MODEL=vertex_ai/gemini-2.5-flash,ENABLE_LLM_PARSING=true
```

## 6. Verify

```powershell
gcloud run services describe planpilot --region us-central1 --format="value(status.url)"
```

Open:

```text
https://YOUR_SERVICE_URL
```

Check:

```text
/healthz
```
