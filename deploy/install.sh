#!/usr/bin/env bash
# Install or update Tech Digest on a systemd-based Linux server.
# Run from the repository root:  sudo ./deploy/install.sh
# Re-running it is safe and acts as an update.
set -euo pipefail

APP_DIR=/opt/tech-digest
APP_USER=techdigest
SRC_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

if [[ $EUID -ne 0 ]]; then
  echo "run as root (sudo $0)" >&2
  exit 1
fi

UV_BIN="$(command -v uv || true)"
if [[ -z "$UV_BIN" ]]; then
  echo "uv not found. Install it first: curl -LsSf https://astral.sh/uv/install.sh | sh" >&2
  exit 1
fi

if ! id "$APP_USER" &>/dev/null; then
  useradd --system --home-dir "$APP_DIR" --shell /usr/sbin/nologin "$APP_USER"
fi

mkdir -p "$APP_DIR/data"
if [[ "$SRC_DIR" != "$APP_DIR" ]]; then
  # Copy code + config; never touch the server's .env or data/.
  tar -C "$SRC_DIR" --exclude=.git --exclude=.venv --exclude=data --exclude=.env \
      --exclude='__pycache__' -cf - . | tar -C "$APP_DIR" -xf -
fi

if [[ ! -f "$APP_DIR/.env" ]]; then
  cp "$APP_DIR/.env.example" "$APP_DIR/.env"
  echo ">> Created $APP_DIR/.env from the example. Edit it with your SMTP settings."
fi
chown -R "$APP_USER:$APP_USER" "$APP_DIR"
chmod 600 "$APP_DIR/.env"

# Python + deps live inside the app dir, owned by the service user.
sudo -u "$APP_USER" env \
  UV_CACHE_DIR="$APP_DIR/.cache/uv" \
  UV_PYTHON_INSTALL_DIR="$APP_DIR/.python" \
  "$UV_BIN" sync --project "$APP_DIR" --frozen --no-dev

install -m 644 "$APP_DIR"/deploy/systemd/techdigest-*.{service,timer} /etc/systemd/system/
systemctl daemon-reload
systemctl enable --now techdigest-collect.timer techdigest-digest.timer

echo
echo "Installed. Next steps:"
echo "  1. sudo -u $APP_USER nano $APP_DIR/.env          # SMTP credentials"
echo "  2. cd $APP_DIR && sudo -u $APP_USER .venv/bin/techdigest send-test"
echo "  3. systemctl list-timers 'techdigest-*'"
