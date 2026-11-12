# ViaCRM Instagram lead bot. Secrets come from an env file at runtime (never baked into the image).
FROM python:3.12-slim
ARG VCS_REF=unknown
LABEL io.viacrm.project=viacrm org.opencontainers.image.revision=$VCS_REF
ENV PYTHONUNBUFFERED=1 DB_PATH=/app/data/agent.db PORT=8080
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt && useradd -r -u 10001 bot && mkdir -p /app/data && chown bot /app/data
COPY brain.py flow.py meta.py notify.py server.py store.py texts.py cli.py check.py ./
USER bot
VOLUME /app/data
EXPOSE 8080
HEALTHCHECK --interval=60s --timeout=5s CMD python -c "import urllib.request;urllib.request.urlopen('http://127.0.0.1:8080/health',timeout=3)"
CMD ["python", "server.py"]
