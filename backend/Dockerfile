# Build context is the repository root (see docker-compose.yml).
FROM python:3.12-slim

WORKDIR /app

COPY backend/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY backend/app ./app
COPY frontend ./frontend
COPY scripts ./scripts
COPY data ./data

EXPOSE 8000

# Load the sample data, then serve. The app itself never reads data/ files.
CMD ["sh", "-c", "python scripts/load_data.py && uvicorn app.main:app --host 0.0.0.0 --port 8000"]
