#!/usr/bin/env bash
set -Eeuo pipefail

ROOT="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

fail() { printf 'ERROR: %s\n' "$*" >&2; exit 1; }

[[ "$(uname -s)" == Linux ]] || fail 'Run this installer on Ubuntu or another Linux host.'
[[ "$(id -u)" -eq 0 ]] || fail 'Run with sudo: sudo bash deploy/ubuntu-install.sh'
command -v docker >/dev/null || fail 'Docker Engine is missing. Install Docker Engine and the Compose plugin, then rerun this command. See https://docs.docker.com/engine/install/ubuntu/'
docker compose version >/dev/null 2>&1 || fail 'Docker Compose v2 plugin is missing.'
command -v openssl >/dev/null || fail 'OpenSSL is missing. Install it with: apt-get install openssl'
[[ -f .env ]] && fail '.env already exists. Refusing to overwrite secrets; back it up and remove it deliberately before reinstalling.'

read -r -p 'Public hostname for this site (example: verify.ncet.co.in): ' PUBLIC_HOST
[[ "$PUBLIC_HOST" =~ ^([a-zA-Z0-9]([a-zA-Z0-9-]{0,61}[a-zA-Z0-9])?\.)+[a-zA-Z]{2,63}$ ]] || fail 'Enter a hostname only, without scheme, port, or path.'
read -r -p 'Initial admin username [admin]: ' ADMIN_USERNAME
ADMIN_USERNAME="${ADMIN_USERNAME:-admin}"
[[ "$ADMIN_USERNAME" =~ ^[a-zA-Z0-9_.@-]{3,64}$ ]] || fail 'Username must be 3-64 letters, digits, or . _ @ - characters.'
read -r -s -p 'Initial admin password (16-128 letters/digits/underscore/hyphen): ' ADMIN_PASSWORD; printf '\n'
[[ ${#ADMIN_PASSWORD} -ge 16 && ${#ADMIN_PASSWORD} -le 128 ]] || fail 'Admin password must be between 16 and 128 characters.'
[[ "$ADMIN_PASSWORD" =~ ^[a-zA-Z0-9_-]+$ ]] || fail 'Use only letters, digits, underscore, and hyphen in this password.'
read -r -s -p 'Confirm admin password: ' ADMIN_PASSWORD_CONFIRM; printf '\n'
[[ "$ADMIN_PASSWORD" == "$ADMIN_PASSWORD_CONFIRM" ]] || fail 'Passwords do not match.'

POSTGRES_PASSWORD="$(openssl rand -hex 32)"
SETTINGS_ENCRYPTION_KEY="$(openssl rand -base64 32 | tr '+/' '-_')"
umask 077
cat > .env <<EOF
APP_ENV=production
PUBLIC_HOST=${PUBLIC_HOST}
PUBLIC_ORIGIN=https://${PUBLIC_HOST}
POSTGRES_PASSWORD=${POSTGRES_PASSWORD}
SETTINGS_ENCRYPTION_KEY=${SETTINGS_ENCRYPTION_KEY}
NCET_BOOTSTRAP_ADMIN_USERNAME=${ADMIN_USERNAME}
NCET_BOOTSTRAP_ADMIN_PASSWORD=${ADMIN_PASSWORD}
SCAN_MODE=off
EOF
unset POSTGRES_PASSWORD SETTINGS_ENCRYPTION_KEY ADMIN_PASSWORD ADMIN_PASSWORD_CONFIRM
chmod 600 .env

docker compose config --quiet || fail 'Compose configuration validation failed; .env was created. Correct the reported issue and rerun docker compose config.'
docker compose up -d --build

printf '\nNCET deployment started. Check status with: docker compose ps\n'
printf 'Required DNS record at your domain provider:\n'
printf '  Type: A\n  Name/Host: %s\n  Value/Points to: this server public IPv4\n  TTL: provider default\n' "$PUBLIC_HOST"
printf '  Optional: add an AAAA record only if this server has working public IPv6.\n'
printf '\nFirewall: allow inbound TCP 80 and 443 (and UDP 443 for HTTP/3).\n'
printf 'Required deployment variables are stored in %s/.env with mode 600. Do not publish that file.\n' "$ROOT"
printf 'After DNS resolves and ports are reachable, verify: https://%s/healthz\n' "$PUBLIC_HOST"
printf 'App key status: settings encryption key is generated and stored privately in .env.\n'
