 #!/usr/bin/env bash
 set -euo pipefail
 
 # Скрипт-подсказка для первичной установки на Ubuntu 22.04/24.04.
 # Запускать от root: sudo bash deploy/ubuntu_setup.sh
 #
 # ВАЖНО:
 # - Скрипт не заполняет токены/ID. Их нужно внести в /opt/tournament-bot/.env вручную.
 # - Репозиторий должен быть уже клонирован в /opt/tournament-bot/app (или положи туда код сам).
 
 if [[ "${EUID}" -ne 0 ]]; then
   echo "Запусти от root: sudo bash deploy/ubuntu_setup.sh"
   exit 1
 fi
 
 BOT_DIR="/opt/tournament-bot"
 APP_DIR="${BOT_DIR}/app"
 VENV_DIR="${BOT_DIR}/venv"
 
 echo "[1/6] Packages"
 apt-get update
 apt-get install -y python3 python3-venv python3-pip git ca-certificates
 
 echo "[2/6] User & dirs"
 id -u tournamentbot >/dev/null 2>&1 || useradd -r -m -d "${BOT_DIR}" -s /usr/sbin/nologin tournamentbot
 mkdir -p "${APP_DIR}" "${BOT_DIR}/data"
 chown -R tournamentbot:tournamentbot "${BOT_DIR}"
 chmod 750 "${BOT_DIR}"
 
 echo "[3/6] venv"
 if [[ ! -x "${VENV_DIR}/bin/python" ]]; then
   python3 -m venv "${VENV_DIR}"
 fi
 "${VENV_DIR}/bin/pip" install --upgrade pip wheel setuptools
 
 echo "[4/6] deps (requirements.txt должен лежать в ${APP_DIR})"
 if [[ ! -f "${APP_DIR}/requirements.txt" ]]; then
   echo "Не найден ${APP_DIR}/requirements.txt. Сначала положи туда проект (main.py/requirements.txt)."
   exit 1
 fi
 "${VENV_DIR}/bin/pip" install -r "${APP_DIR}/requirements.txt"
 
 echo "[5/6] env template"
 if [[ ! -f "${BOT_DIR}/.env" ]]; then
   cat > "${BOT_DIR}/.env" <<'ENV'
 BOT_TOKEN=
 GUILD_ID=
 REGISTRATION_CHANNEL_ID=
 ADMIN_CHANNEL_ID=
 REQUESTS_CHANNEL_ID=
 # Порт для Flask (healthcheck + GSI). Можно оставить 9576 или поменять.
 PORT=9576
 # SQLite на VPS можно хранить прямо на диске:
 DATABASE_PATH=/opt/tournament-bot/data/tournament_bot.db
 ENV
   chown tournamentbot:tournamentbot "${BOT_DIR}/.env"
   chmod 600 "${BOT_DIR}/.env"
 fi
 
 echo "[6/6] systemd"
 install -m 0644 "${APP_DIR}/deploy/systemd/tournament-bot.service" /etc/systemd/system/tournament-bot.service
 systemctl daemon-reload
 systemctl enable tournament-bot.service
 systemctl restart tournament-bot.service
 
 echo ""
 echo "Готово. Проверь статус:"
 echo "  systemctl status tournament-bot --no-pager"
 echo "Логи:"
 echo "  journalctl -u tournament-bot -f"
