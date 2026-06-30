# n8n_portfolio (RSS)

RSS news filtering workflows and the **RSS Python AI sidecar** for the shared [platform-n8n](https://github.com/nanlindev/platform-n8n) stack.

## Layout

- `workflows/` — n8n workflow JSON (import into shared platform)
- `python-service/` — FastAPI sidecar (`rss_python_ai`, port 8001)
- `docker/compose.yml` — sidecar only (no bundled n8n)

## Local dev

```bash
cp .env.example .env
# From repo root:
docker compose -f docker/compose.yml up -d --build
```

Ensure `platform-n8n` networks exist (`../platform-n8n/scripts/ensure-networks.sh`).

## Production

Deployed from `/home/deploy/projects/n8n_portfolio` via GitHub Actions or:

```bash
../platform-n8n/scripts/deploy-sidecars.sh
```

Image: `ghcr.io/nanlindev/n8n_portfolio/python-ai-service:latest`.
