# Multi-stage optimized build for Dokimi Agent A/B Testing Platform
# Stage 1: Build & Dependencies
FROM python:3.12-slim AS builder

WORKDIR /build

RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir --user -r requirements.txt

# Stage 2: Minimal Production Image
FROM python:3.12-slim AS runner

WORKDIR /app

# Create non-root user
RUN groupadd -r dokimi && useradd -r -g dokimi -s /bin/false dokimi

# Copy installed packages from builder
COPY --from=builder /root/.local /home/dokimi/.local
ENV PATH=/home/dokimi/.local/bin:$PATH
ENV PYTHONUNBUFFERED=1

# Copy application files
COPY app/ /app/app/
COPY data/ /app/data/
COPY input/ /app/input/
COPY output/ /app/output/
COPY requirements.txt /app/

RUN chown -R dokimi:dokimi /app
USER dokimi

EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=5s --start-period=5s --retries=3 \
    CMD python3 -c "import urllib.request; urllib.request.urlopen('http://localhost:8000/health')" || exit 1

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
