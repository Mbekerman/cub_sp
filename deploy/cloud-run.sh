#!/usr/bin/env bash
# Publica o monitor como Cloud Run Job e agenda a execução diária no Cloud Scheduler.
#
# Uso:
#   PROJECT_ID=meu-projeto ./deploy/cloud-run.sh
#
# Variáveis opcionais: REGION (padrão southamerica-east1), JOB (cub-sp), REPO (cub-sp),
# SCHEDULE (padrão "0 9 * * *", horário de São Paulo).
#
# Antes da primeira execução, guarde a chave service_role do Supabase no Secret Manager:
#   printf '%s' 'sb_secret_...' | gcloud secrets create cub-sp-supabase-key --data-file=- --project "$PROJECT_ID"
# O script nunca lê a chave; só aponta o job para o segredo.

set -euo pipefail

: "${PROJECT_ID:?defina PROJECT_ID}"
REGION="${REGION:-southamerica-east1}"
JOB="${JOB:-cub-sp}"
REPO="${REPO:-cub-sp}"
SCHEDULE="${SCHEDULE:-0 9 * * *}"
SECRET="${SECRET:-cub-sp-supabase-key}"
SUPABASE_URL="${SUPABASE_URL:-https://mghqcsycuurjezoiiyfp.supabase.co}"
IMAGE="${REGION}-docker.pkg.dev/${PROJECT_ID}/${REPO}/${JOB}:latest"
SA="${JOB}@${PROJECT_ID}.iam.gserviceaccount.com"

gcloud config set project "$PROJECT_ID" >/dev/null

echo "== APIs"
gcloud services enable run.googleapis.com cloudbuild.googleapis.com artifactregistry.googleapis.com \
  cloudscheduler.googleapis.com secretmanager.googleapis.com

echo "== Repositório de imagens"
gcloud artifacts repositories describe "$REPO" --location "$REGION" >/dev/null 2>&1 ||
  gcloud artifacts repositories create "$REPO" --location "$REGION" --repository-format docker

echo "== Conta de serviço do job"
gcloud iam service-accounts describe "$SA" >/dev/null 2>&1 ||
  gcloud iam service-accounts create "$JOB" --display-name "Monitor CUB-SP"
gcloud secrets add-iam-policy-binding "$SECRET" --member "serviceAccount:$SA" \
  --role roles/secretmanager.secretAccessor >/dev/null

echo "== Build da imagem"
gcloud builds submit --tag "$IMAGE" .

echo "== Cloud Run Job"
if gcloud run jobs describe "$JOB" --region "$REGION" >/dev/null 2>&1; then
  ACAO=update
else
  ACAO=create
fi
gcloud run jobs "$ACAO" "$JOB" --region "$REGION" --image "$IMAGE" \
  --service-account "$SA" \
  --set-env-vars "SUPABASE_URL=${SUPABASE_URL},CUB_PASTA_PDFS=/tmp/dados" \
  --set-secrets "SUPABASE_SERVICE_ROLE_KEY=${SECRET}:latest" \
  --max-retries 1 --task-timeout 15m --memory 512Mi

echo "== Agendamento diário (${SCHEDULE}, America/Sao_Paulo)"
PROJECT_NUMBER="$(gcloud projects describe "$PROJECT_ID" --format 'value(projectNumber)')"
SCHED_SA="${PROJECT_NUMBER}-compute@developer.gserviceaccount.com"
gcloud run jobs add-iam-policy-binding "$JOB" --region "$REGION" \
  --member "serviceAccount:$SCHED_SA" --role roles/run.invoker >/dev/null
URI="https://${REGION}-run.googleapis.com/apis/run.googleapis.com/v1/namespaces/${PROJECT_ID}/jobs/${JOB}:run"
if gcloud scheduler jobs describe "$JOB" --location "$REGION" >/dev/null 2>&1; then
  gcloud scheduler jobs update http "$JOB" --location "$REGION" --schedule "$SCHEDULE" \
    --time-zone America/Sao_Paulo --uri "$URI" --http-method POST \
    --oauth-service-account-email "$SCHED_SA"
else
  gcloud scheduler jobs create http "$JOB" --location "$REGION" --schedule "$SCHEDULE" \
    --time-zone America/Sao_Paulo --uri "$URI" --http-method POST \
    --oauth-service-account-email "$SCHED_SA"
fi

echo
echo "Pronto. Para rodar agora: gcloud run jobs execute $JOB --region $REGION --wait"
