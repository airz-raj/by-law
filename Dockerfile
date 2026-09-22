# Mohlat runs as a non-root user on a slim base, with only the runtime
# dependencies installed and only the application and the page copied in.
FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PORT=8080

WORKDIR /srv

COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt

COPY app ./app
COPY web ./web

RUN useradd --system --create-home --uid 10001 mohlat \
    && chown -R mohlat:mohlat /srv
USER mohlat

EXPOSE 8080

# Cloud Run sets $PORT. --proxy-headers lets the app read the client
# address the load balancer forwards, which the rate limiter keys on.
CMD exec uvicorn app.main:create_app --factory \
    --host 0.0.0.0 --port "${PORT}" --proxy-headers --forwarded-allow-ips='*'
