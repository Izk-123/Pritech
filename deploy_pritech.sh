#!/bin/bash
# =============================================================================
# Pritech Project – Full Deployment Script for Ubuntu VPS (Updated)
# Domain: pritechmw.com | Server IP: 204.168.251.91
# Includes Celery, Redis, and environment variables for social auth.
# =============================================================================

set -e  # Exit on any error

echo "====================================================="
echo "Deploying Pritech Project to VPS (with Celery & Redis)"
echo "====================================================="

# -----------------------------------------------------------------------------
# 1. Update system and install system dependencies
# -----------------------------------------------------------------------------
echo "Step 1: Installing system packages..."
sudo apt update
sudo apt install -y python3-pip python3-venv nginx postgresql postgresql-contrib \
                    redis-server git curl certbot python3-certbot-nginx

# Ensure Redis is running
sudo systemctl enable redis-server
sudo systemctl start redis-server

# -----------------------------------------------------------------------------
# 2. Clone or update the repository
# -----------------------------------------------------------------------------
PROJECT_DIR="/home/project/Pritech"
if [ -d "$PROJECT_DIR" ]; then
    echo "Project directory exists. Pulling latest changes..."
    cd $PROJECT_DIR
    git pull origin main
else
    echo "Cloning repository..."
    git clone https://github.com/Izk-123/Pritech.git $PROJECT_DIR
    cd $PROJECT_DIR
fi

# -----------------------------------------------------------------------------
# 3. Set up Python virtual environment and install dependencies
# -----------------------------------------------------------------------------
echo "Step 3: Setting up Python virtual environment..."
if [ ! -d "venv" ]; then
    python3 -m venv venv
fi
source venv/bin/activate
pip install --upgrade pip

# Install core dependencies (including Celery, Redis, etc.)
pip install django gunicorn psycopg2-binary whitenoise python-decouple pillow \
            celery redis django-celery-results

# If requirements.txt exists, install from it (overwrites above but ensures consistency)
if [ -f "requirements.txt" ]; then
    pip install -r requirements.txt
fi

# -----------------------------------------------------------------------------
# 4. Create .env file (skip if already exists)
# -----------------------------------------------------------------------------
ENV_FILE="$PROJECT_DIR/.env"
if [ ! -f "$ENV_FILE" ]; then
    echo "Step 4: Creating .env file. Please provide values (press Enter to use defaults):"
    read -sp "DJANGO_SECRET_KEY (generate random or press Enter for auto): " secret_key
    echo ""
    read -p "DB_NAME (default pritech_db): " db_name
    read -p "DB_USER (default pritech_user): " db_user
    read -sp "DB_PASSWORD: " db_password
    echo ""
    read -p "Domain (default pritechmw.com): " domain
    domain=${domain:-pritechmw.com}
    read -p "Google Client ID (for social login): " google_client_id
    read -sp "Google Secret: " google_secret
    echo ""
    read -p "LinkedIn Client ID: " linkedin_client_id
    read -sp "LinkedIn Secret: " linkedin_secret
    echo ""

    if [ -z "$secret_key" ]; then
        secret_key=$(python -c "from django.core.management.utils import get_random_secret_key; print(get_random_secret_key())")
    fi

    cat > $ENV_FILE <<EOF
DJANGO_SECRET_KEY=${secret_key}
DEBUG=False
ALLOWED_HOSTS=${domain},www.${domain},204.168.251.91,localhost,127.0.0.1
DB_NAME=${db_name:-pritech_db}
DB_USER=${db_user:-pritech_user}
DB_PASSWORD=${db_password:-StrongPritechPass123!}
DB_HOST=localhost
DB_PORT=5432
REDIS_URL=redis://localhost:6379/0
GOOGLE_CLIENT_ID=${google_client_id}
GOOGLE_SECRET=${google_secret}
LINKEDIN_CLIENT_ID=${linkedin_client_id}
LINKEDIN_SECRET=${linkedin_secret}
EMAIL_HOST=smtp.gmail.com
EMAIL_PORT=587
EMAIL_USE_TLS=True
EMAIL_HOST_USER=admin@${domain}
EMAIL_HOST_PASSWORD=your-app-password
DEFAULT_FROM_EMAIL=noreply@${domain}
EOF
    echo ".env file created. Please edit later to set real email credentials if needed."
else
    echo ".env already exists. Skipping (you may need to add missing variables manually)."
    # Load current .env to use variables later
    source $ENV_FILE
fi

# -----------------------------------------------------------------------------
# 5. Setup PostgreSQL (skip if already exists)
# -----------------------------------------------------------------------------
source $ENV_FILE
DB_NAME=${DB_NAME:-pritech_db}
DB_USER=${DB_USER:-pritech_user}
DB_PASSWORD=${DB_PASSWORD:-StrongPritechPass123!}

echo "Step 5: Ensuring PostgreSQL database exists..."
sudo -u postgres psql -tc "SELECT 1 FROM pg_database WHERE datname = '${DB_NAME}'" | grep -q 1 || \
    sudo -u postgres psql -c "CREATE DATABASE ${DB_NAME} OWNER ${DB_USER};"

sudo -u postgres psql -tc "SELECT 1 FROM pg_roles WHERE rolname = '${DB_USER}'" | grep -q 1 || \
    sudo -u postgres psql -c "CREATE USER ${DB_USER} WITH PASSWORD '${DB_PASSWORD}';"

sudo -u postgres psql -c "ALTER ROLE ${DB_USER} SET client_encoding TO 'utf8';"
sudo -u postgres psql -c "ALTER USER ${DB_USER} CREATEDB;"
sudo -u postgres psql -c "GRANT ALL PRIVILEGES ON DATABASE ${DB_NAME} TO ${DB_USER};"

# -----------------------------------------------------------------------------
# 6. Run migrations, collect static, create superuser if needed
# -----------------------------------------------------------------------------
echo "Step 6: Running Django migrations and collecting static..."
python manage.py makemigrations
python manage.py migrate
python manage.py collectstatic --noinput

echo "Creating superuser (interactive) – skip if already exists."
python manage.py createsuperuser || echo "Superuser may already exist."

# -----------------------------------------------------------------------------
# 7. Create systemd service for Gunicorn (if not exists)
# -----------------------------------------------------------------------------
SERVICE_FILE="/etc/systemd/system/gunicorn-pritch.service"
if [ ! -f "$SERVICE_FILE" ]; then
    echo "Step 7: Creating Gunicorn systemd service..."
    sudo tee $SERVICE_FILE > /dev/null <<EOF
[Unit]
Description=Gunicorn for Pritech Project
After=network.target redis.target

[Service]
User=root
Group=root
WorkingDirectory=$PROJECT_DIR
Environment="PATH=$PROJECT_DIR/venv/bin"
Environment="DJANGO_SETTINGS_MODULE=Pritech.settings"
EnvironmentFile=$ENV_FILE
ExecStart=$PROJECT_DIR/venv/bin/gunicorn --workers 3 --bind unix:$PROJECT_DIR/gunicorn.sock Pritech.wsgi:application
Restart=on-failure

[Install]
WantedBy=multi-user.target
EOF
    sudo systemctl daemon-reload
    sudo systemctl enable gunicorn-pritch
fi
sudo systemctl restart gunicorn-pritch

# -----------------------------------------------------------------------------
# 8. Create systemd services for Celery worker and beat
# -----------------------------------------------------------------------------
echo "Step 8: Creating Celery systemd services..."

# Celery worker
CELERY_WORKER_SERVICE="/etc/systemd/system/celery-worker.service"
if [ ! -f "$CELERY_WORKER_SERVICE" ]; then
    sudo tee $CELERY_WORKER_SERVICE > /dev/null <<EOF
[Unit]
Description=Celery Worker for Pritech
After=network.target redis.target

[Service]
User=root
Group=root
WorkingDirectory=$PROJECT_DIR
Environment="PATH=$PROJECT_DIR/venv/bin"
Environment="DJANGO_SETTINGS_MODULE=Pritech.settings"
EnvironmentFile=$ENV_FILE
ExecStart=$PROJECT_DIR/venv/bin/celery -A Pritech worker -l info
Restart=on-failure

[Install]
WantedBy=multi-user.target
EOF
    sudo systemctl daemon-reload
    sudo systemctl enable celery-worker
fi
sudo systemctl restart celery-worker

# Celery beat (for periodic tasks)
CELERY_BEAT_SERVICE="/etc/systemd/system/celery-beat.service"
if [ ! -f "$CELERY_BEAT_SERVICE" ]; then
    sudo tee $CELERY_BEAT_SERVICE > /dev/null <<EOF
[Unit]
Description=Celery Beat for Pritech
After=network.target redis.target

[Service]
User=root
Group=root
WorkingDirectory=$PROJECT_DIR
Environment="PATH=$PROJECT_DIR/venv/bin"
Environment="DJANGO_SETTINGS_MODULE=Pritech.settings"
EnvironmentFile=$ENV_FILE
ExecStart=$PROJECT_DIR/venv/bin/celery -A Pritech beat -l info --scheduler django_celery_beat.schedulers:DatabaseScheduler
Restart=on-failure

[Install]
WantedBy=multi-user.target
EOF
    sudo systemctl daemon-reload
    sudo systemctl enable celery-beat
fi
sudo systemctl restart celery-beat

# -----------------------------------------------------------------------------
# 9. Configure Nginx (HTTP only, SSL later)
# -----------------------------------------------------------------------------
echo "Step 9: Configuring Nginx..."
domain=${domain:-pritechmw.com}
NGINX_SITE="/etc/nginx/sites-available/pritechmw"
if [ ! -f "$NGINX_SITE" ]; then
    sudo tee $NGINX_SITE > /dev/null <<EOF
server {
    listen 80;
    server_name ${domain} www.${domain};

    location /static/ {
        alias $PROJECT_DIR/staticfiles/;
    }

    location /media/ {
        alias $PROJECT_DIR/media/;
    }

    location / {
        include proxy_params;
        proxy_pass http://unix:$PROJECT_DIR/gunicorn.sock;
    }
}
EOF
    sudo ln -sf $NGINX_SITE /etc/nginx/sites-enabled/
    sudo rm -f /etc/nginx/sites-enabled/default
fi
sudo nginx -t && sudo systemctl restart nginx

# -----------------------------------------------------------------------------
# 10. Obtain SSL certificate (if not already)
# -----------------------------------------------------------------------------
echo "Step 10: Attempting SSL certificate (skip if already present)..."
if sudo certbot --nginx -d ${domain} -d www.${domain} --non-interactive --agree-tos --email admin@${domain} 2>/dev/null; then
    echo "SSL certificate obtained."
    sudo systemctl reload nginx
else
    echo "Certbot failed – DNS may not be propagated yet. Run manually later:"
    echo "  sudo certbot --nginx -d ${domain} -d www.${domain}"
fi

# -----------------------------------------------------------------------------
# 11. Final status and info
# -----------------------------------------------------------------------------
echo "====================================================="
echo "✅ Pritech deployment completed (with Celery & Redis)!"
echo ""
echo "Services status:"
sudo systemctl status gunicorn-pritch --no-pager --lines=0
sudo systemctl status celery-worker --no-pager --lines=0
sudo systemctl status celery-beat --no-pager --lines=0
sudo systemctl status nginx --no-pager --lines=0
echo ""
echo "====================================================="
echo "Visit: https://${domain} (once DNS/SSL ready)"
echo "Admin: https://${domain}/admin"
echo ""
echo "Useful commands:"
echo "  sudo journalctl -u gunicorn-pritch -f"
echo "  sudo journalctl -u celery-worker -f"
echo "  sudo journalctl -u celery-beat -f"
echo "====================================================="
