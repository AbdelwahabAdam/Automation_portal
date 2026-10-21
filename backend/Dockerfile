FROM python:3.12-slim
WORKDIR /app

# Pango for weasyprint (the receipt PDF), and a font with Arabic letters
RUN apt-get update \
    && apt-get install -y --no-install-recommends libpango-1.0-0 libpangoft2-1.0-0 libharfbuzz-subset0 fonts-noto-core \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

# Which version this image is, written in by the deploy (deploy/ansible/roles/pipeline)
ARG APP_VERSION=dev
ARG APP_BUILD=0
ARG APP_COMMIT=
ARG APP_BUILT_AT=
ENV APP_VERSION=$APP_VERSION APP_BUILD=$APP_BUILD APP_COMMIT=$APP_COMMIT APP_BUILT_AT=$APP_BUILT_AT

EXPOSE 8001
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8001"]
