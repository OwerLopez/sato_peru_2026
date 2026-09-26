# API de SATO-AQP (FastAPI + Uvicorn), imagen liviana sin dependencias de ML
FROM python:3.12-slim AS base
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 PIP_NO_CACHE_DIR=1
WORKDIR /app
COPY requirements-api.txt .
RUN pip install -r requirements-api.txt
COPY sato/__init__.py sato/config.py sato/
COPY sato/api sato/api
COPY sato/services sato/services
RUN useradd --create-home --uid 10001 sato && mkdir -p /app/data /app/artifacts && chown -R sato /app
USER sato
EXPOSE 8000
HEALTHCHECK --interval=30s --timeout=5s --start-period=20s --retries=3 \
  CMD python -c "import urllib.request,sys; sys.exit(0 if urllib.request.urlopen('http://127.0.0.1:8000/api/health').status==200 else 1)"
CMD ["uvicorn", "sato.api.main:app", "--host", "0.0.0.0", "--port", "8000", "--workers", "2", "--proxy-headers", "--forwarded-allow-ips", "*"]
