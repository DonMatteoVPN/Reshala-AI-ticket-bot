# Stage 1: Builder
FROM python:3.12-slim as builder

WORKDIR /app

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

RUN pip install --upgrade pip

# Create and install user dependencies
RUN useradd -m appuser
USER appuser

COPY --chown=appuser:appuser backend/requirements.txt requirements.txt
RUN pip install --user --no-cache-dir -r requirements.txt

# Stage 2: Runtime
FROM python:3.12-slim

WORKDIR /app

# Install curl for healthcheck
RUN apt-get update && apt-get install -y --no-install-recommends curl && rm -rf /var/lib/apt/lists/*

# Create non-root user
RUN useradd -m appuser
USER appuser

# Copy installed dependencies
COPY --from=builder /home/appuser/.local /home/appuser/.local

# Environment
ENV PATH=/home/appuser/.local/bin:$PATH
ENV PYTHONPATH=/app/backend

# Copy application code
COPY --chown=appuser:appuser backend ./backend
# Copy configuration if needed (e.g. .env is usually mounted or injected)

# Expose port
EXPOSE 8000

# Healthcheck
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD curl --fail http://localhost:8000/api/health || exit 1

# Run command
CMD ["uvicorn", "backend.server:app", "--host", "0.0.0.0", "--port", "8000"]
