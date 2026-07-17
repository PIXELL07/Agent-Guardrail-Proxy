# Build stage: install dependencies into a venv ---
    FROM python:3.12-slim AS builder

    WORKDIR /app
    
    RUN python -m venv /venv
    ENV PATH="/venv/bin:$PATH"
    
    COPY requirements.txt .
    RUN pip install --no-cache-dir -r requirements.txt
    
    # Runtime stage: copy only the venv + app code, not build tooling ---
    FROM python:3.12-slim
    
    WORKDIR /app
    
    RUN useradd --create-home --uid 1000 appuser
    COPY --from=builder /venv /venv
    ENV PATH="/venv/bin:$PATH"
    
    COPY app/ ./app/
    
    RUN mkdir -p /data && chown -R appuser:appuser /app /data
    USER appuser
    
    ENV DB_PATH=/data/guardrail.db
    
    EXPOSE 8000
    
    HEALTHCHECK --interval=30s --timeout=3s --start-period=10s \
      CMD python -c "import httpx; httpx.get('http://localhost:8000/health').raise_for_status()" || exit 1
    
    CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
    