FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    FIXUPXER_DB_PATH=/data/bot_stats.db

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY fixupxer_bot.py ./
COPY cleaners/ ./cleaners/

# Persist SQLite DB across container restarts.
RUN mkdir -p /data
VOLUME ["/data"]

# Drop privileges.
RUN useradd --create-home --uid 10001 bot && chown -R bot:bot /data /app
USER bot

CMD ["python", "fixupxer_bot.py"]
