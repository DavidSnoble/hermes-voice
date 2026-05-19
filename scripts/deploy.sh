#!/usr/bin/env bash
set -euo pipefail

APP_DIR="/opt/hermes-voice"
REPO_URL="https://github.com/DavidSnoble/hermes-voice.git"
SERVICE_NAME="hermes-voice"
PORT=9120
DOMAIN="voice.dsnoble.com"

echo "==> Deploying Hermes Voice..."

# 1. Clone or update code
if [[ -d "$APP_DIR/.git" ]]; then
    cd "$APP_DIR"
    git pull origin main
else
    rm -rf "$APP_DIR"
    git clone "$REPO_URL" "$APP_DIR"
    cd "$APP_DIR"
fi

# 2. Python env
cd "$APP_DIR"
if [[ ! -d ".venv" ]]; then
    python3 -m venv .venv
fi
source .venv/bin/activate
pip install -q -U pip
pip install -q -e ".[dev]"

# 3. Environment file must exist
if [[ ! -f "$APP_DIR/.env" ]]; then
    echo "ERROR: $APP_DIR/.env missing. Copy .env.example and fill in keys:"
    echo "  DEEPGRAM_API_KEY=..."
    echo "  CARTESIA_API_KEY=..."
    exit 1
fi

# 4. Systemd service
cat > /etc/systemd/system/${SERVICE_NAME}.service <<EOF
[Unit]
Description=Hermes Voice
After=network.target hermes-gateway.service
Wants=hermes-gateway.service

[Service]
Type=simple
User=root
WorkingDirectory=${APP_DIR}
Environment=PYTHONPATH=${APP_DIR}/src
EnvironmentFile=${APP_DIR}/.env
ExecStart=${APP_DIR}/.venv/bin/uvicorn hermes_voice.api.main:app --host 0.0.0.0 --port ${PORT}
Restart=always
RestartSec=5

[Install]
WantedBy=multi-user.target
EOF

systemctl daemon-reload
systemctl enable "$SERVICE_NAME"
systemctl restart "$SERVICE_NAME"

# 5. Nginx config
cat > /etc/nginx/sites-available/${SERVICE_NAME} <<EOF
server {
    listen 443 ssl http2;
    server_name ${DOMAIN};

    ssl_certificate /etc/letsencrypt/live/${DOMAIN}/fullchain.pem;
    ssl_certificate_key /etc/letsencrypt/live/${DOMAIN}/privkey.pem;
    ssl_protocols TLSv1.2 TLSv1.3;

    location / {
        proxy_pass http://127.0.0.1:${PORT};
        proxy_http_version 1.1;
        proxy_set_header Upgrade \$http_upgrade;
        proxy_set_header Connection 'upgrade';
        proxy_set_header Host \$host;
        proxy_set_header X-Real-IP \$remote_addr;
        proxy_set_header X-Forwarded-For \$proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto \$scheme;
        proxy_read_timeout 86400;
    }
}

server {
    listen 80;
    server_name ${DOMAIN};
    return 301 https://\$host\$request_uri;
}
EOF

ln -sf /etc/nginx/sites-available/${SERVICE_NAME} /etc/nginx/sites-enabled/

# 6. SSL cert
if [[ ! -d "/etc/letsencrypt/live/${DOMAIN}" ]]; then
    certbot --nginx -d "$DOMAIN" --non-interactive --agree-tos --email snoble1353@gmail.com
else
    certbot renew --quiet || true
fi

nginx -t && systemctl reload nginx

echo "==> Hermes Voice deployed to https://${DOMAIN}"
echo "==> Status: systemctl status ${SERVICE_NAME}"
