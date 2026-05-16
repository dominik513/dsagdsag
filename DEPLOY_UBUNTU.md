 # Деплой Discord-бота на Ubuntu VPS (systemd)
 
 Ниже инструкция “безопасно и круто”: отдельный linux-пользователь, виртуальное окружение, автозапуск через systemd, логи через journalctl.
 
 ## 0) Что подготовить в Discord Developer Portal
 1. Включи intents, которые использует бот:
    - **SERVER MEMBERS INTENT** (если используется members)
    - **MESSAGE CONTENT INTENT** (если используется message_content)
 2. Скопируй:
    - `BOT_TOKEN`
    - ID сервера (guild) → `GUILD_ID`
    - ID каналов → `REGISTRATION_CHANNEL_ID`, `ADMIN_CHANNEL_ID`, `REQUESTS_CHANNEL_ID`
 
 ## 1) Подключение к серверу
 ```bash
 ssh root@<IP_СЕРВЕРА>
 ```
 
 ## 2) Куда ставим
 Рекомендуемый путь установки:
 - `/opt/tournament-bot/app` — код (где лежит `main.py`)
 - `/opt/tournament-bot/venv` — виртуальное окружение
 - `/opt/tournament-bot/data` — SQLite база
 - `/opt/tournament-bot/.env` — переменные окружения (секреты)
 
 ## 3) Клонируем репозиторий
 ```bash
 mkdir -p /opt/tournament-bot
 cd /opt/tournament-bot
 git clone <ССЫЛКА_НА_ТВОЙ_GITHUB_REPO> app
 ```
 
 Проверь, что файлы на месте:
 ```bash
 ls -la /opt/tournament-bot/app
 # должен быть main.py и requirements.txt
 ```
 
 ## 4) Авто-установка (рекомендую)
 В репозитории уже лежит скрипт:
 ```bash
 sudo bash /opt/tournament-bot/app/deploy/ubuntu_setup.sh
 ```
 
 Он:
 - создаст пользователя `tournamentbot`
 - создаст venv и поставит зависимости
 - создаст `/opt/tournament-bot/.env` (шаблон)
 - установит systemd-сервис `tournament-bot`
 
 ## 5) Заполняем .env (ОБЯЗАТЕЛЬНО)
 Открой файл:
 ```bash
 sudo nano /opt/tournament-bot/.env
 ```
 Заполни минимум:
 - `BOT_TOKEN=...`
 - `GUILD_ID=...`
 - `REGISTRATION_CHANNEL_ID=...`
 - `ADMIN_CHANNEL_ID=...`
 - `REQUESTS_CHANNEL_ID=...`
 
 Базу лучше хранить так:
 - `DATABASE_PATH=/opt/tournament-bot/data/tournament_bot.db`
 
 После правки перезапусти сервис:
 ```bash
 sudo systemctl restart tournament-bot
 ```
 
 ## 6) Проверка статуса и логов
 Статус:
 ```bash
 sudo systemctl status tournament-bot --no-pager
 ```
 Логи в реальном времени:
 ```bash
 sudo journalctl -u tournament-bot -f
 ```
 
 ## 7) Открытие порта (если нужен внешний доступ к Flask/GSI)
 Бот сам по себе порт не требует, но у тебя есть Flask (`/health`, `/gsi`).
 Если хочешь принимать GSI извне, открой порт (пример для `PORT=9576`):
 ```bash
 sudo ufw allow 9576/tcp
 sudo ufw enable
 sudo ufw status
 ```
 
 **Если внешний GSI не нужен** — порт можно не открывать.
 
 ## 8) Обновление (redeploy) без простоя “вручную”
 ```bash
 cd /opt/tournament-bot/app
 sudo -u tournamentbot git pull
 sudo systemctl restart tournament-bot
 sudo journalctl -u tournament-bot -n 100 --no-pager
 ```
 
 ## 9) Частые проблемы
 ### Discord пишет “application did not respond”
 Значит команда слишком поздно ответила на interaction. В коде мы уже добавили `defer` и безопасные ответы, но если VPS слабый — увеличивай ресурсы/убирай тяжёлые операции из начала команд.
 
 ### База “слетает”
 На VPS это происходит только если ты:
 - удалил файл базы,
 - поменял `DATABASE_PATH`,
 - или права на папку неверные.
 Проверь:
 ```bash
 ls -la /opt/tournament-bot/data
 ```
 
 ## 10) (Опционально) HTTPS и домен
 Если хочешь принимать `/gsi` по HTTPS, обычно ставят Nginx + certbot и проксируют на `127.0.0.1:9576`.
 Скажи домен — добавлю готовый nginx-конфиг.
