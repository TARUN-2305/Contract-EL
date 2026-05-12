FROM python:3.11-slim

WORKDIR /app

# System deps for pdfplumber, psycopg2, sentence-transformers
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc g++ libpq-dev poppler-utils libmagic1 curl \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir --default-timeout=1000 --retries 10 -r requirements.txt

COPY . .

# Create data directories
RUN mkdir -p /app/data/rule_store /app/data/audit /app/data/uploads \
             /app/data/reports /app/data/risk /app/data/compliance

EXPOSE 8000

CMD ["uvicorn", "api.main:app", "--host", "0.0.0.0", "--port", "8000", "--timeout-keep-alive", "300"]
