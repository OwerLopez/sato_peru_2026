# Pipeline de datos / ML / carga de BD (sin GPU; los embeddings se recalculan aparte)
FROM python:3.12-slim
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 PIP_NO_CACHE_DIR=1
RUN apt-get update && apt-get install -y --no-install-recommends unzip libgomp1 && rm -rf /var/lib/apt/lists/*
WORKDIR /app
COPY requirements-api.txt requirements.txt ./
RUN pip install -r requirements.txt
COPY sato sato
COPY db db
RUN useradd --create-home --uid 10001 sato && chown -R sato /app
USER sato
ENTRYPOINT ["python", "-m"]
CMD ["sato.serving.load_db"]
