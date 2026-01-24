# Aegis Bridge - Supabase to Archon72 petition integration

FROM python:3.11-slim

WORKDIR /app

# Install dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application
COPY src/ src/
COPY main.py .

# Create non-root user
RUN useradd -m -u 1000 bridge && chown -R bridge:bridge /app
USER bridge

# Default command: single batch run
# Override with --continuous for polling mode
ENTRYPOINT ["python", "main.py"]
