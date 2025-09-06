FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    DEBIAN_FRONTEND=noninteractive

WORKDIR /app

# Use HTTPS mirrors and add retries to make apt more reliable
RUN set -eux; \
    sed -i 's|http://|https://|g' /etc/apt/sources.list || true; \
    if [ -f /etc/apt/sources.list.d/debian.sources ]; then sed -i 's|http://|https://|g' /etc/apt/sources.list.d/debian.sources; fi; \
    apt-get -o Acquire::Retries=5 update; \
    apt-get -o Acquire::Retries=5 install -y --no-install-recommends \
        ca-certificates \
        poppler-utils \
        ffmpeg \
        libreoffice \
        fonts-dejavu \
        fonts-noto-core \
        fonts-noto-cjk \
        fonts-noto-color-emoji; \
    rm -rf /var/lib/apt/lists/*

COPY requirements.txt /app/requirements.txt
RUN pip install --no-cache-dir -r requirements.txt

COPY . /app

EXPOSE 5000
CMD ["uvicorn", "app:app", "--host", "0.0.0.0", "--port", "5000"]
