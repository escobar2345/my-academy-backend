# ============================================================
# my-academy-backend - Railway / Docker image (API only).
#
# This repository IS the former backend/ folder, so the paths are
# flat (deploy_server.py, run.py, app/ ... all sit at /app).
# The monorepo's ..\Dockerfile builds frontend + backend together;
# this one builds the backend service on its own.
#
# deploy_server.py serves all three Flask apps (main boirsu app,
# api_server, partner_auth) on ONE port ($PORT, injected by Railway)
# and picks the right app per URL prefix - the same routing the Vite
# dev proxy does locally.
#
# The Vue frontend is NOT in this repo. It is built and hosted
# separately (escobar2345/my-academy-frontend) and reaches this API
# over its public URL, so no frontend/dist is bundled here.
# ============================================================
FROM python:3.11-slim

WORKDIR /app

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

# Python dependencies first so the layer cache survives code edits.
# NOTE: this installs requirements.txt (NOT pyproject.toml) - the
# pyproject dependency list is incomplete for the boi-rsu scripts.
COPY requirements.txt ./
RUN pip install --upgrade pip \
 && pip install -r requirements.txt

# Application source
COPY . .

# Teacher PDFs / generated lessons / textbook output.
# Attach a Railway Volume mounted at /app/uploads to persist these
# between deploys - without a volume the folder resets every build.
RUN mkdir -p /app/uploads

# deploy_server.py binds 0.0.0.0:$PORT (Railway injects PORT; 8000 locally)
EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=10s --start-period=90s --retries=3 \
  CMD python -c "import os,urllib.request;urllib.request.urlopen('http://127.0.0.1:'+os.environ.get('PORT','8000')+'/healthz').read()"

CMD ["python", "deploy_server.py"]
