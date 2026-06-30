#!/bin/bash
# NEOGEN — Déploiement VPS Hostinger (Ubuntu 24.04 LTS)
# Lancer directement sur le VPS : bash deploy-vps.sh
# IP : 76.13.53.162 | Domaine : neogen.netroia.tech
set -e

DOMAIN="neogen.netroia.tech"
REPO="https://github.com/captainNetroia/NEOGEN.git"
APP_DIR="/opt/neogen"
EMAIL="captain@netroia.com"

echo "=== NEOGEN DEPLOY ==="
echo "Domaine : $DOMAIN"
echo "Dossier : $APP_DIR"

# ── 1. Docker ────────────────────────────────────────────────────────────────
if ! command -v docker &>/dev/null; then
  echo "[1/6] Installation Docker..."
  apt-get update -qq
  apt-get install -y ca-certificates curl gnupg lsb-release
  install -m 0755 -d /etc/apt/keyrings
  curl -fsSL https://download.docker.com/linux/ubuntu/gpg | gpg --dearmor -o /etc/apt/keyrings/docker.gpg
  echo "deb [arch=$(dpkg --print-architecture) signed-by=/etc/apt/keyrings/docker.gpg] https://download.docker.com/linux/ubuntu $(lsb_release -cs) stable" > /etc/apt/sources.list.d/docker.list
  apt-get update -qq
  apt-get install -y docker-ce docker-ce-cli containerd.io docker-compose-plugin
  systemctl enable docker --now
  echo "  Docker $(docker --version) ✓"
else
  echo "[1/6] Docker déjà installé : $(docker --version)"
fi

# ── 2. Cloner / MAJ NEOGEN ───────────────────────────────────────────────────
echo "[2/6] Clonage NEOGEN..."
if [ -d "$APP_DIR/.git" ]; then
  git -C "$APP_DIR" pull --ff-only
  echo "  MAJ git ✓"
else
  git clone "$REPO" "$APP_DIR"
  echo "  Clone ✓"
fi

# ── 3. Fichier .env ──────────────────────────────────────────────────────────
echo "[3/6] Fichier .env..."
ENV_FILE="$APP_DIR/.env"
if [ ! -f "$ENV_FILE" ]; then
  read -rp "  Clé Anthropic (sk-ant-...) : " ANT_KEY
  cat > "$ENV_FILE" <<EOF
ANTHROPIC_API_KEY=$ANT_KEY
NEOGEN_BASE_URL=https://$DOMAIN
NEOGEN_OWNER_EMAIL=$EMAIL
NEOGEN_CORS_ORIGINS=https://$DOMAIN
NEOGEN_OWNER_UNLIMITED=0
NEOGEN_ALLOW_DEFAULT_KEY=0
EOF
  chmod 600 "$ENV_FILE"
  echo "  .env créé ✓"
else
  echo "  .env déjà présent ✓"
fi

# ── 4. Lancer NEOGEN (prod) ──────────────────────────────────────────────────
echo "[4/6] Docker Compose prod..."
cd "$APP_DIR"
docker compose -f docker-compose.prod.yml pull --quiet 2>/dev/null || true
docker compose -f docker-compose.prod.yml up -d --build
echo "  Conteneurs démarrés ✓"
sleep 3
STATUS=$(curl -s -o /dev/null -w "%{http_code}" http://127.0.0.1:8000/health)
echo "  Health check : $STATUS"
[ "$STATUS" = "200" ] || { echo "  ERREUR : API non joignable (attendre 10s et relancer)"; }

# ── 5. Nginx ─────────────────────────────────────────────────────────────────
echo "[5/6] Nginx..."
if ! command -v nginx &>/dev/null; then
  apt-get install -y nginx
fi
NGINX_CONF="/etc/nginx/sites-available/neogen"
cat > "$NGINX_CONF" <<NGINX
server {
    listen 80;
    server_name $DOMAIN;
    return 301 https://\$host\$request_uri;
}
server {
    listen 443 ssl http2;
    server_name $DOMAIN;
    ssl_certificate     /etc/letsencrypt/live/$DOMAIN/fullchain.pem;
    ssl_certificate_key /etc/letsencrypt/live/$DOMAIN/privkey.pem;
    ssl_protocols       TLSv1.2 TLSv1.3;
    ssl_ciphers         HIGH:!aNULL:!MD5;
    add_header Strict-Transport-Security "max-age=31536000; includeSubDomains" always;
    add_header X-Frame-Options SAMEORIGIN always;
    add_header X-Content-Type-Options nosniff always;
    limit_req_zone \$binary_remote_addr zone=neogen:10m rate=10r/s;
    limit_req zone=neogen burst=20 nodelay;
    proxy_read_timeout 120s;
    proxy_connect_timeout 10s;
    location / {
        proxy_pass         http://127.0.0.1:8000;
        proxy_http_version 1.1;
        proxy_set_header   Upgrade \$http_upgrade;
        proxy_set_header   Connection "upgrade";
        proxy_set_header   Host \$host;
        proxy_set_header   X-Real-IP \$remote_addr;
        proxy_set_header   X-Forwarded-For \$proxy_add_x_forwarded_for;
        proxy_set_header   X-Forwarded-Proto \$scheme;
    }
    client_max_body_size 20M;
}
NGINX
ln -sf "$NGINX_CONF" /etc/nginx/sites-enabled/neogen
rm -f /etc/nginx/sites-enabled/default
nginx -t && systemctl reload nginx
echo "  Nginx configuré ✓"

# ── 6. SSL Certbot ───────────────────────────────────────────────────────────
echo "[6/6] SSL Let's Encrypt..."
if ! command -v certbot &>/dev/null; then
  apt-get install -y certbot python3-certbot-nginx
fi
# Nginx temporairement en HTTP pour le challenge
sed -i 's/listen 443 ssl http2/listen 80/' "$NGINX_CONF"
sed -i '/ssl_/d' "$NGINX_CONF"
nginx -t && systemctl reload nginx
certbot certonly --nginx -d "$DOMAIN" --email "$EMAIL" --agree-tos --non-interactive
# Remettre la config HTTPS complète
cat > "$NGINX_CONF" <<NGINX
server {
    listen 80;
    server_name $DOMAIN;
    return 301 https://\$host\$request_uri;
}
server {
    listen 443 ssl http2;
    server_name $DOMAIN;
    ssl_certificate     /etc/letsencrypt/live/$DOMAIN/fullchain.pem;
    ssl_certificate_key /etc/letsencrypt/live/$DOMAIN/privkey.pem;
    ssl_protocols       TLSv1.2 TLSv1.3;
    ssl_ciphers         HIGH:!aNULL:!MD5;
    add_header Strict-Transport-Security "max-age=31536000; includeSubDomains" always;
    add_header X-Frame-Options SAMEORIGIN always;
    add_header X-Content-Type-Options nosniff always;
    limit_req_zone \$binary_remote_addr zone=neogen:10m rate=10r/s;
    limit_req zone=neogen burst=20 nodelay;
    proxy_read_timeout 120s;
    proxy_connect_timeout 10s;
    location / {
        proxy_pass         http://127.0.0.1:8000;
        proxy_http_version 1.1;
        proxy_set_header   Upgrade \$http_upgrade;
        proxy_set_header   Connection "upgrade";
        proxy_set_header   Host \$host;
        proxy_set_header   X-Real-IP \$remote_addr;
        proxy_set_header   X-Forwarded-For \$proxy_add_x_forwarded_for;
        proxy_set_header   X-Forwarded-Proto \$scheme;
    }
    client_max_body_size 20M;
}
NGINX
nginx -t && systemctl reload nginx
echo "  SSL ✓"

echo ""
echo "================================================"
echo "  NEOGEN EN LIGNE : https://$DOMAIN"
echo "  Health : curl https://$DOMAIN/health"
echo "  Logs   : docker logs neogen-api -f"
echo "  MAJ    : cd $APP_DIR && bash update.sh"
echo "================================================"
