FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1
ENV PIP_DISABLE_PIP_VERSION_CHECK=1

WORKDIR /app

RUN apt-get update \
    && apt-get install -y --no-install-recommends curl xvfb xauth \
    && rm -rf /var/lib/apt/lists/*

COPY pyproject.toml /app/
RUN mkdir -p /app/src/bettingmaster && touch /app/src/bettingmaster/__init__.py \
    && pip install --upgrade pip \
    && pip install -e . \
    && python -m playwright install --with-deps chromium \
    && python -m playwright install --with-deps chrome

COPY alembic.ini /app/
COPY alembic /app/alembic
COPY src /app/src
COPY data /app/data
COPY docker /app/docker

EXPOSE 8000
