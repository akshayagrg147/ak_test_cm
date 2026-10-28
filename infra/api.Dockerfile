FROM python:3.12-slim-bookworm
ARG VCS_REF=development
LABEL io.viacrm.project=viacrm org.opencontainers.image.revision=$VCS_REF
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1
WORKDIR /app
COPY backend/requirements.lock .
RUN pip install --no-cache-dir -r requirements.lock && useradd --uid 10001 --create-home crm && mkdir /storage && chown crm:crm /storage
COPY backend/ .
USER crm
EXPOSE 8010
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8010", "--no-access-log"]
