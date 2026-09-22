# Deploying Mohlat

Two ways to give the container a model. Option A is preferred: there is no
API key anywhere, because Cloud Run's service identity authenticates to
Vertex AI directly.

Everything below assumes `gcloud` is installed and you are logged in.

```bash
export PROJECT_ID="your-project-id"
export REGION="asia-south1"
gcloud config set project "$PROJECT_ID"

gcloud services enable \
  run.googleapis.com \
  cloudbuild.googleapis.com \
  artifactregistry.googleapis.com \
  aiplatform.googleapis.com
```

## Option A: Vertex AI through the service identity

No key is created, stored or rotated. The container authenticates as its own
service account.

```bash
gcloud iam service-accounts create mohlat-run \
  --display-name "Mohlat Cloud Run service account"

gcloud projects add-iam-policy-binding "$PROJECT_ID" \
  --member "serviceAccount:mohlat-run@${PROJECT_ID}.iam.gserviceaccount.com" \
  --role "roles/aiplatform.user"

gcloud run deploy mohlat \
  --source . \
  --region "$REGION" \
  --service-account "mohlat-run@${PROJECT_ID}.iam.gserviceaccount.com" \
  --allow-unauthenticated \
  --memory 512Mi --cpu 1 --concurrency 40 \
  --min-instances 0 --max-instances 3 --timeout 60 \
  --set-env-vars "APP_ENV=prod,TRUST_PROXY=true,LLM_BACKEND=vertex,GCP_PROJECT=${PROJECT_ID},GCP_LOCATION=global,GEMINI_MODEL=gemini-flash-latest"
```

`GCP_LOCATION` must be a location that serves the chosen model. `global` works
for the Flash-tier models at the time of writing; check the model's page in the
Vertex AI console before deploying, and set the region explicitly if `global`
is not offered.

## Option B: an AI Studio key held in Secret Manager

Use this when Vertex AI is not available on the project. The key never appears
in an environment variable you can read from the console, and never in the
repository.

```bash
gcloud services enable secretmanager.googleapis.com

printf '%s' "$GEMINI_API_KEY" | gcloud secrets create gemini-api-key --data-file=-

gcloud secrets add-iam-policy-binding gemini-api-key \
  --member "serviceAccount:$(gcloud projects describe "$PROJECT_ID" \
      --format='value(projectNumber)')-compute@developer.gserviceaccount.com" \
  --role "roles/secretmanager.secretAccessor"

gcloud run deploy mohlat \
  --source . \
  --region "$REGION" \
  --allow-unauthenticated \
  --memory 512Mi --cpu 1 --concurrency 40 \
  --min-instances 0 --max-instances 3 --timeout 60 \
  --set-secrets "GEMINI_API_KEY=gemini-api-key:latest" \
  --set-env-vars "APP_ENV=prod,TRUST_PROXY=true,LLM_BACKEND=aistudio,GEMINI_MODEL=gemini-flash-latest"
```

## Why these settings

| Setting | Reason |
|---|---|
| `APP_ENV=prod` | Turns off the interactive API docs. `/api/openapi.json` stays available. |
| `TRUST_PROXY=true` | Cloud Run sets `X-Forwarded-For`; the rate limiter keys on it. Leave it false anywhere a caller could set that header themselves. |
| `--min-instances 0` | Scales to zero between requests, so an idle app costs nothing. |
| `--concurrency 40` | One model call per request, most of it spent waiting, so a single instance serves many at once. |
| `--max-instances 3` | A ceiling on spend. Raise it if you expect real traffic. |
| `--timeout 60` | Longer than the 30-second model timeout, short enough that a stuck request does not hold an instance. |

## After deploying

```bash
URL="$(gcloud run services describe mohlat --region "$REGION" --format='value(status.url)')"

curl -s "$URL/api/v1/health"
curl -s "$URL/api/v1/rules" | head -c 400
curl -sI "$URL/" | grep -iE "content-security-policy|strict-transport|x-content-type|referrer-policy"

curl -s -X POST "$URL/api/v1/notices/decode" \
  -F "text=$(cat web/samples/cheque-demand-notice.txt)" \
  -F "receipt_date=$(date -I)" | head -c 600
```

Then open the URL, run each sample through, load the rent agreement into the
cross-check, and print the briefing sheet.

## Rolling back

```bash
gcloud run revisions list --service mohlat --region "$REGION"
gcloud run services update-traffic mohlat --region "$REGION" --to-revisions "REVISION=100"
```

## Logs

Structured JSON, one object per line, so Cloud Logging parses the fields.

```bash
gcloud run services logs read mohlat --region "$REGION" --limit 50
```

Logs record the request id, route, status, latency and whether the result came
from the cache. They never record document text, prompts or model output.
