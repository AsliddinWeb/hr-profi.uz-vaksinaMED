FROM python:3.12-slim AS base
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1
WORKDIR /srv
RUN useradd --create-home --uid 1000 app
# Yuz modellari (alohida qatlam: kod o'zgarganda qayta yuklanmaydi)
COPY scripts/fetch_models.py /tmp/fetch_models.py
RUN python /tmp/fetch_models.py /opt/models
ENV FACE_MODEL_DIR=/opt/models

FROM base AS dev
ENV RUFF_CACHE_DIR=/tmp/.ruff_cache PYTEST_ADDOPTS="-p no:cacheprovider"
COPY requirements.txt requirements-dev.txt ./
RUN --mount=type=cache,target=/root/.cache/pip pip install -r requirements-dev.txt
COPY . .
USER app
CMD ["sh", "-c", "python -m app.migrate && uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload"]

FROM base AS prod
COPY requirements.txt ./
RUN --mount=type=cache,target=/root/.cache/pip pip install -r requirements.txt
COPY . .
USER app
CMD ["sh", "-c", "python -m app.migrate && uvicorn app.main:app --host 0.0.0.0 --port 8000 --proxy-headers --forwarded-allow-ips='*'"]
