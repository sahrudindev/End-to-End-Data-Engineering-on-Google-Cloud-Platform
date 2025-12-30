# =============================================================================
# E-commerce Event Data Generator - Dockerfile
# =============================================================================
# Simplified build for lower memory environments
# =============================================================================

FROM python:3.11-slim

# Security: Run as non-root user
RUN groupadd --gid 1000 appgroup && \
    useradd --uid 1000 --gid appgroup --shell /bin/bash --create-home appuser

WORKDIR /app

# Install Python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY --chown=appuser:appgroup main.py .

# Set environment variables
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    NUM_EVENTS=100 \
    BATCH_SIZE=100 \
    PUBSUB_TOPIC=ecommerce-events

# Switch to non-root user
USER appuser

# Default command
ENTRYPOINT ["python", "main.py"]
CMD ["--help"]
