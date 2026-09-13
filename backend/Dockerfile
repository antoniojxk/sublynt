FROM python:3.12-slim AS runtime
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1
WORKDIR /app
COPY pyproject.toml ./
COPY app ./app
COPY sublynt_core ./sublynt_core
COPY alembic.ini ./
COPY alembic ./alembic
RUN pip install --no-cache-dir .
RUN mkdir -p /app/data/files
EXPOSE 8000
CMD ["sh", "-c", "if [ -z \"$SUBLYNT_STORAGE_BUCKET\" ]; then alembic upgrade head; fi && exec uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-8000}"]
