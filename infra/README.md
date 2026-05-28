# Azure deployment

This directory holds the Bicep templates that provision the production
stack on Azure. Sized for the **Azure for Students** ($100/yr) credit
ceiling — every resource is on the cheapest tier that still supports
the app's requirements.

## The stack

| Resource | SKU | Cost (after free offers) |
|---|---|---|
| Azure Database for PostgreSQL Flexible Server | Burstable B1ms, 32 GB | ~$13/mo (free for 12 months on new accounts) |
| Container Apps Environment + App | Consumption, 0.5 vCPU / 1 GiB, scale-to-zero | $0 under free monthly grant (180k vCPU-sec) |
| Static Web App | Free tier | $0 |
| Log Analytics workspace | PerGB2018 | $0 under 5 GB free monthly grant |

**Why this shape:** Postgres + pgvector is mandatory (semantic search,
RAG). Container Apps with scale-to-zero is the cheapest way to run a
FastAPI service on Azure — between cron fires the app uses no compute.
Static Web Apps Free is free forever for personal sites.

Container images come from **ghcr.io** (free for public repos) instead
of Azure Container Registry (~$5/mo Basic tier).

## First-time deploy

```bash
# 1. Log in and create the resource group.
az login
az group create --name mai-news-rg --location westeurope

# 2. Generate a strong Postgres admin password.
export PG_PWD=$(openssl rand -base64 24)

# 3. Deploy the stack.
az deployment group create \
  --resource-group mai-news-rg \
  --template-file main.bicep \
  --parameters main.parameters.json \
  --parameters postgresAdminPassword="$PG_PWD"

# 4. Set runtime secrets on the Container App. Replace the placeholders.
az containerapp secret set \
  --name mainews-api \
  --resource-group mai-news-rg \
  --secrets \
    jwt-secret=$(openssl rand -base64 48) \
    entra-tenant-id=<your-tenant-id> \
    entra-client-id=<your-client-id> \
    entra-client-secret=<your-entra-secret> \
    openai-api-key=<sk-...> \
    anthropic-api-key=<sk-ant-...> \
    resend-api-key=<re_...> \
    worker-shared-secret=$(openssl rand -base64 32)

# 5. Roll the app to pick up the new secrets.
az containerapp update --name mainews-api --resource-group mai-news-rg
```

The deployment outputs the Container App URL and Static Web App default
hostname — grab those for the next step.

## Wire CORS once the frontend has a URL

```bash
az deployment group create \
  --resource-group mai-news-rg \
  --template-file main.bicep \
  --parameters main.parameters.json \
  --parameters postgresAdminPassword="$PG_PWD" \
  --parameters frontendUrl="https://<your-swa>.azurestaticapps.net"
```

## CI/CD

`.github/workflows/deploy-backend.yml` rebuilds the image and rolls the
Container App on every push to `main` that touches backend code. Set
three GitHub secrets:

| Secret | Value |
|---|---|
| `AZURE_CREDENTIALS` | output of `az ad sp create-for-rbac --name mai-news-deploy --role contributor --scopes /subscriptions/<sub>/resourceGroups/mai-news-rg --sdk-auth` |
| `AZURE_RESOURCE_GROUP` | `mai-news-rg` |
| `CONTAINER_APP_NAME` | `mainews-api` |

Frontend deploys via the auto-generated Static Web Apps workflow (visible
in the SWA blade in the portal — copy the deployment token, add it as
`AZURE_STATIC_WEB_APPS_API_TOKEN`).

## Cost watch

The single biggest cost driver after the 12-month free Postgres offer
expires is the database. After 12 months either:

- migrate to **Neon free tier** (still Postgres + pgvector, costs $0); or
- accept ~$13/mo for the Burstable B1ms on Azure (~$160/yr — would
  consume most of a renewed student credit).

Container Apps scale-to-zero keeps compute cost negligible at MVP
traffic. The hourly digest cron is ~30s of compute per fire = ~12
vCPU-minutes/day; well inside the free grant.

## Tear it all down

```bash
az group delete --name mai-news-rg --yes --no-wait
```
