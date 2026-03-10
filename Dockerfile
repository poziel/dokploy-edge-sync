FROM python:3.12-alpine

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /app

RUN apk add --no-cache tzdata

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY app /app/app
COPY edge_sync.py /app/edge_sync.py
COPY docker/entrypoint.sh /entrypoint.sh
RUN chmod +x /entrypoint.sh

RUN mkdir -p /app/config /app/data /etc/traefik/dynamic

ENTRYPOINT ["/entrypoint.sh"]