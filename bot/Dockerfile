FROM python:3.11-slim

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    libpq-dev \
    && rm -rf /var/lib/apt/lists/*

COPY pyproject.toml .
RUN pip install --no-cache-dir --upgrade pip setuptools && pip install --no-cache-dir -e .

COPY . .

CMD ["sh", "-c", "alembic upgrade head && python -m src.main"]
