# Deploying VerifyLens (internal server)

One Docker container serves the website and the API. The database lives in a
Docker volume. Secrets are files on the server, never in the image.

## 1. One-time server setup

Needs Docker Engine + the Compose plugin (Ubuntu: `sudo apt install docker.io docker-compose-v2`).

```bash
# Secrets: one file each, readable only by the container user (uid 10001)
sudo mkdir -p /etc/verifylens
python3 -c "import secrets; print(secrets.token_urlsafe(48))" | sudo tee /etc/verifylens/jwt_secret_key >/dev/null
sudo sh -c 'printf "%s" "PASTE-GEMINI-KEY-HERE" > /etc/verifylens/gemini_api_key'
sudo chown 10001 /etc/verifylens/* && sudo chmod 400 /etc/verifylens/*

# Backup folder
sudo mkdir -p /srv/verifylens-backups && sudo chown 10001 /srv/verifylens-backups
```

## 2. Start

```bash
cd task03
BACKUP_DIR=/srv/verifylens-backups docker compose up -d --build
docker compose ps           # STATUS should become "healthy"
docker compose logs -f app  # Ctrl+C to stop following
```

The app listens on `127.0.0.1:8000` only. Put your internal reverse proxy
(nginx/Caddy with HTTPS) or VPN in front of it, and set
`FORWARDED_ALLOW_IPS=<proxy IP>` so rate limits see real user IPs.

## 3. First admin (new database only)

```bash
docker compose exec app python -m scripts.bootstrap_admin --username admin
```

### Moving the existing database instead

```bash
cd backend && python -m scripts.backup_db --dest ../migrate   # on the old machine
docker compose cp ./migrate/search_history-*.db app:/data/search_history.db
docker compose restart app
```

## 4. Daily backups (host crontab)

```cron
0 2 * * * cd /path/to/task03 && docker compose exec -T app python -m scripts.backup_db --keep 14
```

Copy `/srv/verifylens-backups` to another machine too.
**Restore:** `docker compose stop app`, copy a backup to `/data/search_history.db`
(as above), delete any `-wal`/`-shm` files next to it, `docker compose start app`.

## 5. Everyday tasks

| Task | Command |
|---|---|
| Update to new code | `git pull && docker compose up -d --build` |
| User forgot password | Admin: **User management → Edit existing account → Reset password** |
| Only admin forgot password | `docker compose exec app python -m scripts.reset_password --username admin` |
| Rotate login secret | Replace `/etc/verifylens/jwt_secret_key`, `docker compose restart app` (everyone is logged out) |

## Rules

- **Run one container only.** SQLite and the rate limits don't support several copies.
- The database must be on a local disk (Docker volume), not a network share.
- The schema upgrades itself at startup (it only adds columns); take a backup before updating anyway.
