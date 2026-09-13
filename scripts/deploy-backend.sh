#!/usr/bin/env bash
set -euo pipefail

: "${GCP_BACKEND_PROJECT_ID:?Required}"
: "${GCP_REGION:?Required}"
: "${SUBLYNT_STORAGE_BUCKET:?Required}"
: "${GCP_RUNTIME_SERVICE_ACCOUNT:?Required}"
: "${IMAGE:?Required}"

gcloud run deploy sublynt-api \
  --project="$GCP_BACKEND_PROJECT_ID" \
  --region="$GCP_REGION" \
  --image="$IMAGE" \
  --service-account="$GCP_RUNTIME_SERVICE_ACCOUNT" \
  --port=8080 --cpu=1 --memory=512Mi \
  --min=0 --max=1 --concurrency=1 --timeout=60 \
  --set-env-vars="^|^SUBLYNT_ENVIRONMENT=production|SUBLYNT_STORAGE_BUCKET=$SUBLYNT_STORAGE_BUCKET|SUBLYNT_RETENTION_HOURS=24|SUBLYNT_DEMO_LIMITS_ENABLED=true|SUBLYNT_CORS_ORIGINS=https://sublynt.web.app,https://sublynt.firebaseapp.com" \
  --quiet
