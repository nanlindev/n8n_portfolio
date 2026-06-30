# RSS Project Deployment

Deploy the RSS Python sidecar. Shared n8n runs in `platform-n8n`.

## Prerequisites

- `platform-n8n` running (`docker compose -f docker/compose.yml up -d`)
- `n8n_platform` network exists (`../platform-n8n/scripts/ensure-networks.sh`)
- OBS stacks on `proxy_network` (optional)

## Local

```bash
cd /home/lotey/lindev/n8n_portfolio
cp docker/.env.example .env   # or copy from root .env.example
docker compose -f docker/compose.yml up -d --build
```

Sidecar: http://localhost:8001/health

## Production

Path: `/home/deploy/projects/n8n_portfolio`

Push to `main` triggers GitHub Actions (builds GHCR image, deploys sidecar).

Manual:

```bash
cd /home/deploy/projects/n8n_portfolio
../platform-n8n/scripts/ensure-networks.sh
docker pull ghcr.io/nanlindev/n8n_portfolio/python-ai-service:latest
docker compose -f docker/compose.yml up -d
```

## n8n workflow

Import `workflows/RSS News Filter.json` into shared n8n.

Sidecar URL: `http://rss_python_ai:8001/analyze`

## GHCR image

`ghcr.io/nanlindev/n8n_portfolio/python-ai-service:latest`
