#!/bin/bash
# =============================================================================
# Pritech Project – Full Deployment Script for Ubuntu VPS
# Domain: pritechmw.com | Server IP: 204.168.251.91
# =============================================================================

set -e  # Exit on any error

echo "====================================================="
echo "Deploying Pritech Project to VPS"
echo "====================================================="

# -----------------------------------------------------------------------------
# 1. Update system and install system dependencies
# -----------------------------------------------------------------------------
echo "Step 1: Installing system packages..."
sudo apt update
sudo apt install -y python3-pip python3-venv nginx postgresql postgresql-contrib \
                    redis-server git curl certbot python3-certbot-nginx

# -----------------------------------------------------------------------------
# 2. Clone or update the repository
# -----------------------------------------------------------------------------
cd /home/project
if [ -d "Pritech" ]; then
    echo "Project directory exists. Pulling latest changes..."
    cd Pritech
    git pull origin main
else
    echo "Cloning repository..."
    git clone https://github.com/Izk-123/Pritech.git Pritech
    cd Pritech
fi

# -----------------------------------------------------------------------------
# 3. Set up Python virtual environment and install dependencies
# -----------------------------------------------------------------------------
echo "Step 3: Setting up Python virtual environment..."
python3 -m venv venv
source venv/bin/activate
pip install --upgrade pip
pip install django gunicorn psycopg2-binary whitenoise python-decouple pillow

# If requirements.txt exists, use it
if [ -f "requirements.txt" ]; then
    pip install -r requirements.txt
fi

# -----------------------------------------------------------------------------
# 4. Create .env file (skip if already exists)
# -----------------------------------------------------------------------------
if [ ! -f ".env" ]; then
    echo "Step 4: Creating .env file. Please provide values:"
    read -sp "DJANGO_SECRET_KEY (generate random or press Enter for auto): " secret_key
    echo ""
    read -p "DB_NAME (default pritech_db): " db_name
    read -p "DB_USER (default pritech_user): " db_user
    read -sp "DB_PASSWORD: " db_password
    echo ""
    read -p "Domain (default pritechmw.com): " domain
    domain=${domain:-pritechmw.com}

    if [ -z "$secret_key" ]; then
        secret_key=$(python -c "from django.core.management.utils import get_random_secret_key; print(get_random_secret_key())")
    fi

    cat > .env <<EOF
DJANGO_SECRET_KEY=${secret_key}
DEBUG=False
ALLOWED_HOSTS=${domain},www.${domain},204.168.251.91,localhost,127.0.0.1
DB_NAME=${db_name:-pritech_db}
DB_USER=${db_user:-pritech_user}
DB_PASSWORD=${db_password:-StrongPritechPass123!}
DB_HOST=localhost
DB_PORT=5432
EOF
    echo ".env file created."
else
    echo ".env already exists. Skipping."
fi

# -----------------------------------------------------------------------------
# 5. Create PostgreSQL database and user
# -----------------------------------------------------------------------------
# Extract DB_NAME and DB_USER from .env (or use defaults)
source .env
DB_NAME=${DB_NAME:-pritech_db}
DB_USER=${DB_USER:-pritech_user}
DB_PASSWORD=${DB_PASSWORD:-StrongPritechPass123!}

echo "Step 5: Setting up PostgreSQL..."
sudo -u postgres psql <<EOF
DROP DATABASE IF EXISTS ${DB_NAME};
DROP USER IF EXISTS ${DB_USER};
CREATE USER ${DB_USER} WITH PASSWORD '${DB_PASSWORD}';
CREATE DATABASE ${DB_NAME} OWNER ${DB_USER};
ALTER ROLE ${DB_USER} SET client_encoding TO 'utf8';
ALTER USER ${DB_USER} CREATEDB;
GRANT ALL PRIVILEGES ON DATABASE ${DB_NAME} TO ${DB_USER};
EOF

# -----------------------------------------------------------------------------
# 6. Run migrations, collect static, create superuser
# -----------------------------------------------------------------------------
echo "Step 6: Running Django migrations and collecting static..."
python manage.py makemigrations
python manage.py migrate
python manage.py collectstatic --noinput

echo "Creating superuser (interactive)..."
python manage.py createsuperuser

# -----------------------------------------------------------------------------
# 7. Create systemd service for Gunicorn
# -----------------------------------------------------------------------------
echo "Step 7: Setting up Gunicorn systemd service..."
sudo tee /etc/systemd/system/gunicorn-pritch.service > /dev/null <<EOF
[Unit]
Description=Gunicorn for Pritech Project
After=network.target

[Service]
User=root
Group=root
WorkingDirectory=/home/project/Pritech
Environment="PATH=/home/project/Pritech/venv/bin"
Environment="DJANGO_SETTINGS_MODULE=Pritech.settings"
EnvironmentFile=/home/project/Pritech/.env
ExecStart=/home/project/Pritech/venv/bin/gunicorn --workers 3 --bind unix:/home/project/Pritech/gunicorn.sock Pritech.wsgi:application
Restart=on-failure

[Install]
WantedBy=multi-user.target
EOF

sudo systemctl daemon-reload
sudo systemctl enable gunicorn-pritch
sudo systemctl restart gunicorn-pritch

# -----------------------------------------------------------------------------
# 8. Configure Nginx (HTTP only, SSL will be added later)
# -----------------------------------------------------------------------------
echo "Step 8: Configuring Nginx..."
domain=${domain:-pritechmw.com}
sudo tee /etc/nginx/sites-available/pritechmw > /dev/null <<EOF
server {
    listen 80;
    server_name ${domain} www.${domain};

    location /static/ {
        alias /home/project/Pritech/staticfiles/;
    }

    location /media/ {
        alias /home/project/Pritech/media/;
    }

    location / {
        include proxy_params;
        proxy_pass http://unix:/home/project/Pritech/gunicorn.sock;
    }
}
EOF

sudo ln -sf /etc/nginx/sites-available/pritechmw /etc/nginx/sites-enabled/
sudo rm -f /etc/nginx/sites-enabled/default
sudo nginx -t && sudo systemctl restart nginx

# -----------------------------------------------------------------------------
# 9. Obtain SSL certificate if domain resolves (optional)
# -----------------------------------------------------------------------------
echo "Step 9: Attempting SSL certificate (ensure DNS points to this VPS)..."
if sudo certbot --nginx -d ${domain} -d www.${domain} --non-interactive --agree-tos --email admin@${domain} 2>/dev/null; then
    echo "SSL certificate obtained."
    # Update .env to enable HTTPS if needed (optional)
    # sed -i 's/HTTPS_ENABLED=false/HTTPS_ENABLED=true/' .env
    sudo systemctl restart gunicorn-pritch
    sudo systemctl reload nginx
else
    echo "Certbot failed – DNS may not be propagated yet. Run manually later:"
    echo "  sudo certbot --nginx -d ${domain} -d www.${domain}"
fi

# -----------------------------------------------------------------------------
# 10. Final status and info
# -----------------------------------------------------------------------------
echo "====================================================="
echo "Pritech deployment completed!"
sudo systemctl status gunicorn-pritch --no-pager
echo "Nginx status:"
sudo systemctl status nginx --no-pager
echo "====================================================="
echo "Visit: https://${domain} (once DNS/SSL ready)"
echo "Admin: https://${domain}/admin"
echo "Logs: sudo journalctl -u gunicorn-pritch -f"
echo "====================================================="
