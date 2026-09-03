#!/usr/bin/env bash
set -euo pipefail

PHOENIX_VERSION="3.0.0"
DOMAIN="${PHOENIX_DOMAIN:-phoenix.example.com}"
EMAIL="${PHOENIX_SSL_EMAIL:-admin@example.com}"
GATEWAY_PORT="${PHOENIX_GATEWAY_PORT:-8080}"
API_PORT="${PHOENIX_API_PORT:-8000}"

info() { echo -e "[INFO] $*"; }
ok()   { echo -e "[OK] $*"; }
fail() { echo -e "[FAIL] $*"; exit 1; }

install_prereqs() {
    info "Installing prerequisites..."
    if ! command -v docker >/dev/null 2>&1; then
        info "Installing Docker..."
        curl -fsSL https://get.docker.com | sh
        systemctl enable --now docker
    fi
    if ! command -v docker-compose >/dev/null 2>&1 && ! docker compose version >/dev/null 2>&1; then
        info "Installing Docker Compose..."
        curl -L "https://github.com/docker/compose/releases/latest/download/docker-compose-$(uname -s)-$(uname -m)" -o /usr/local/bin/docker-compose
        chmod +x /usr/local/bin/docker-compose
    fi
    if ! command -v nginx >/dev/null 2>&1; then
        info "Installing Nginx..."
        if command -v apt-get >/dev/null 2>&1; then apt-get update && apt-get install -y nginx; fi
        if command -v yum >/dev/null 2>&1; then yum install -y nginx; fi
    fi
    if ! command -v certbot >/dev/null 2>&1; then
        info "Installing Certbot..."
        if command -v apt-get >/dev/null 2>&1; then apt-get install -y certbot python3-certbot-nginx; fi
        if command -v yum >/dev/null 2>&1; then yum install -y certbot python3-certbot-nginx; fi
    fi
    ok "Prerequisites installed"
}

write_dockerfile() {
    info "Writing Dockerfile..."
    cat > Dockerfile <<'EOF'
FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential curl && rm -rf /var/lib/apt/lists/*

WORKDIR /app
COPY backend/requirements.txt ./requirements.txt
RUN pip install --no-cache-dir -r requirements.txt

COPY backend ./backend

EXPOSE 8000

CMD ["uvicorn", "cloud.api_server:app", "--host", "0.0.0.0", "--port", "8000", "--workers", "4"]
EOF
    ok "Dockerfile written"
}

write_docker_compose() {
    info "Writing docker-compose.yml..."
    cat > docker-compose.yml <<'EOF'
version: "3.9"

services:
  api:
    build: .
    image: phoenix-cloud:${PHOENIX_VERSION:-3.0.0}
    restart: always
    ports:
      - "127.0.0.1:8000:8000"
    environment:
      - DATABASE_URL=postgresql://phoenix:phoenix@postgres:5432/phoenix
      - REDIS_HOST=redis
      - REDIS_PORT=6379
      - PHOENIX_JWT_SECRET=${PHOENIX_JWT_SECRET}
    depends_on:
      postgres:
        condition: service_healthy
      redis:
        condition: service_healthy
    healthcheck:
      test: ["CMD", "curl", "-f", "http://localhost:8000/health"]
      interval: 30s
      timeout: 5s
      retries: 3
    labels:
      - "prometheus.io/scrape=true"
      - "prometheus.io/port=8000"

  postgres:
    image: postgres:16-alpine
    restart: always
    environment:
      POSTGRES_USER: phoenix
      POSTGRES_PASSWORD: phoenix
      POSTGRES_DB: phoenix
    volumes:
      - pgdata:/var/lib/postgresql/data
    ports:
      - "127.0.0.1:5432:5432"
    healthcheck:
      test: ["CMD-SHELL", "pg_isready -U phoenix"]
      interval: 10s
      timeout: 5s
      retries: 5

  redis:
    image: redis:7-alpine
    restart: always
    command: ["redis-server", "--requirepass", "${REDIS_PASSWORD:-phoenix}"]
    volumes:
      - redisdata:/data
    ports:
      - "127.0.0.1:6379:6379"
    healthcheck:
      test: ["CMD", "redis-cli", "ping"]
      interval: 10s
      timeout: 5s
      retries: 5

  nginx:
    image: nginx:1.25-alpine
    restart: always
    ports:
      - "80:80"
      - "443:443"
    volumes:
      - ./nginx/nginx.conf:/etc/nginx/nginx.conf:ro
      - ./nginx/conf.d:/etc/nginx/conf.d:ro
      - certbot/www:/var/www/certbot
      - certbot/conf:/etc/letsencrypt
    depends_on:
      - api

  prometheus:
    image: prom/prometheus:v2.45.0
    restart: always
    volumes:
      - ./monitoring/prometheus.yml:/etc/prometheus/prometheus.yml:ro
      - promdata:/prometheus
    command:
      - '--config.file=/etc/prometheus/prometheus.yml'
      - '--storage.tsdb.path=/prometheus'
      - '--storage.tsdb.retention.time=30d'
    ports:
      - "127.0.0.1:9090:9090"

  grafana:
    image: grafana/grafana:10.2.0
    restart: always
    environment:
      - GF_SECURITY_ADMIN_PASSWORD=${GRAFANA_PASSWORD:-admin}
    volumes:
      - grafanadata:/var/lib/grafana
      - ./monitoring/grafana:/etc/grafana/provisioning:ro
    ports:
      - "127.0.0.1:3000:3000"

  certbot:
    image: certbot/certbot:v2.9.0
    volumes:
      - certbot/www:/var/www/certbot
      - certbot/conf:/etc/letsencrypt
    entrypoint: "/bin/sh -c 'trap exit TERM; while :; do certbot renew; sleep 12h & wait $${!}; done;'"

volumes:
  pgdata:
  redisdata:
  promdata:
  grafanadata:
EOF
    ok "docker-compose.yml written"
}

write_nginx_conf() {
    info "Writing Nginx config..."
    mkdir -p nginx/conf.d certbot/www certbot/conf
    cat > nginx/nginx.conf <<'EOF'
user nginx;
worker_processes auto;
error_log /var/log/nginx/error.log warn;
pid /var/run/nginx.pid;

events {
    worker_connections 1024;
}

http {
    log_format main '$remote_addr - $remote_user [$time_local] "$request" $status $body_bytes_sent "$http_referer" "$http_user_agent"';
    access_log /var/log/nginx/access.log main;

    sendfile on;
    tcp_nopush on;
    keepalive_timeout 65;
    types_hash_max_size 2048;

    include /etc/nginx/mime.types;
    default_type application/octet-stream;

    upstream api_backend {
        server api:8000;
    }

    server {
        listen 80;
        server_name ${DOMAIN};

        location /.well-known/acme-challenge/ {
            root /var/www/certbot;
        }

        location / {
            return 301 https://$host$request_uri;
        }
    }

    server {
        listen 443 ssl http2;
        server_name ${DOMAIN};

        ssl_certificate /etc/letsencrypt/live/${DOMAIN}/fullchain.pem;
        ssl_certificate_key /etc/letsencrypt/live/${DOMAIN}/privkey.pem;
        ssl_protocols TLSv1.2 TLSv1.3;
        ssl_ciphers ECDHE-ECDSA-AES128-GCM-SHA256:ECDHE-RSA-AES128-GCM-SHA256:ECDHE-ECDSA-AES256-GCM-SHA384:ECDHE-RSA-AES256-GCM-SHA384;
        ssl_prefer_server_ciphers off;
        ssl_session_cache shared:SSL:10m;
        ssl_session_timeout 10m;

        add_header Strict-Transport-Security "max-age=63072000; includeSubDomains; preload" always;
        add_header X-Frame-Options SAMEORIGIN;
        add_header X-Content-Type-Options nosniff;
        add_header X-XSS-Protection "1; mode=block";

        client_max_body_size 50m;

        location / {
            proxy_pass http://api_backend;
            proxy_set_header Host $host;
            proxy_set_header X-Real-IP $remote_addr;
            proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
            proxy_set_header X-Forwarded-Proto $scheme;
            proxy_connect_timeout 30s;
            proxy_read_timeout 60s;
            proxy_send_timeout 60s;
        }

        location /metrics {
            proxy_pass http://api_backend;
            allow 127.0.0.1;
            deny all;
        }
    }
}
EOF
    ok "Nginx config written"
}

write_prometheus() {
    info "Writing Prometheus config..."
    mkdir -p monitoring
    cat > monitoring/prometheus.yml <<'EOF'
global:
  scrape_interval: 15s
  evaluation_interval: 15s

scrape_configs:
  - job_name: "phoenix-api"
    static_configs:
      - targets: ["api:8000"]
    metrics_path: "/metrics"

  - job_name: "node"
    static_configs:
      - targets: ["host.docker.internal:9100"]
EOF
    ok "Prometheus config written"
}

setup_ssl() {
    info "Setting up SSL with Let's Encrypt..."
    if [ ! -d "/etc/letsencrypt/live/${DOMAIN}" ]; then
        docker compose down || true
        docker compose up -d nginx
        sleep 2
        certbot certonly --webroot -w /tmp/certbot -d "${DOMAIN}" --email "${EMAIL}" --agree-tos --no-eff-email || fail "Certbot failed"
    else
        info "SSL certificates already exist, skipping"
    fi
    ok "SSL configured"
}

deploy_stack() {
    info "Building and starting stack..."
    docker compose down || true
    docker compose build
    docker compose up -d
    ok "Stack deployed"
}

verify() {
    info "Verifying deployment..."
    sleep 5
    if curl -sf http://localhost:8000/health >/dev/null 2>&1; then
        ok "API health check passed"
    else
        fail "API health check failed"
    fi
    if curl -sf http://localhost:9090/-/healthy >/dev/null 2>&1; then
        ok "Prometheus healthy"
    else
        fail "Prometheus not healthy"
    fi
    if curl -sf "http://localhost:3000/api/health" >/dev/null 2>&1; then
        ok "Grafana healthy"
    else
        fail "Grafana not healthy"
    fi
    info "Dashboard: http://localhost:3000 (admin / ${GRAFANA_PASSWORD:-admin})"
    info "API docs:  https://${DOMAIN}/docs"
}

main() {
    info "Phoenix Cloud Deployment v${PHOENIX_VERSION}"
    info "Domain: ${DOMAIN}"
    install_prereqs
    write_dockerfile
    write_docker_compose
    write_nginx_conf
    write_prometheus
    setup_ssl
    deploy_stack
    verify
    ok "Deployment complete!"
}

main "$@"
