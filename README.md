# 🌤 Weather Parser Telegram Bot (Санкт-Петербург)

Асинхронный Telegram-бот прогноза погоды с ежедневной автоматической рассылкой в **07:00 по МСК**, базой данных подписчиков на **SQLite + SQLAlchemy (async)**, контейнеризацией в **Docker** и автоматическим **CI/CD деплоем на сервер через GitHub Actions**.

---

## 📋 Возможности

* ⏰ **Ежедневная рассылка в 07:00 МСК**: каждое утро бот отправляет актуальный прогноз погоды всем активным подписчикам.
* 📊 **Подробная сводка на день**:
  * Температура и «ощущается как» для **Утра (08:00)**, **Дня (14:00)** и **Вечера (20:00)**.
  * Текстовое описание погодных условий и эмодзи (ясно, пасмурно, морось, дождь, гроза и т.д.).
  * Осадки (вероятность в % и ожидаемое количество в мм).
  * Ветер (скорость в м/с, порывы и градация: слабый, умеренный, сильный, штормовой).
  * Умные контекстные советы («Не забудьте зонт ☂️», «Одевайтесь теплее 🧣» и др.).
* 💬 **Интерактивные команды**:
  * `/start` — регистрация в базе данных и подписка на рассылку (+ приветственный прогноз).
  * `/weather` — получить свежий прогноз на сегодня прямо сейчас.
  * `/stop` — отписаться от утренней рассылки (сохраняя профиль в базе).
  * `/stats` — просмотр статистики активных подписчиков.
  * `/help` — список всех доступных команд.
* 🛡 **Отказоустойчивость**:
  * Автоматическое выявление и отписка пользователей, заблокировавших бота, без сбоя общей рассылки.
  * Паузы между отправками сообщений для соблюдения лимитов Telegram API (Flood control).
  * Персистентное хранение базы данных SQLite в Docker volume.

---

## 🛠 Стек технологий

* **Язык**: Python 3.12+ (асинхронный)
* **Telegram Bot API**: `pyTelegramBotAPI` (`telebot.async_telebot.AsyncTeleBot`)
* **База данных**: `SQLite` + `SQLAlchemy 2.x (asyncio)` + `aiosqlite`
* **Источник погоды**: `Open-Meteo API` (бесплатный, стабильный, без ограничений и ключей)
* **Планировщик задач**: `APScheduler` (`AsyncIOScheduler`) с таймзоной `Europe/Moscow`
* **Контейнеризация**: `Docker`, `Docker Compose`
* **CI/CD**: `GitHub Actions` -> `Docker Hub` -> `SSH Deploy` на ваш сервер

---

## 📁 Структура проекта

```text
weatherparser/
├── app/
│   ├── config.py             # Настройки и чтение переменных окружения
│   ├── main.py               # Точка входа: запуск бота, планировщика и БД
│   ├── db/
│   │   ├── models.py         # SQLAlchemy модель пользователя (User)
│   │   ├── session.py        # Асинхронный движок и создание таблиц
│   │   └── crud.py           # Операции с базой (добавление, отписка, выборка)
│   ├── handlers/
│   │   └── commands.py       # Обработчики команд (/start, /weather, /stop, /help, /stats)
│   ├── scheduler/
│   │   └── broadcast.py      # Логика ежедневной рассылки в 07:00
│   └── services/
│       └── weather.py        # Запрос к Open-Meteo и форматирование сводки
├── data/                     # Директория для файла SQLite (weather.db)
├── .github/
│   └── workflows/
│       └── deploy.yml        # CI/CD пайплайн для сборки и деплоя
├── Dockerfile                # Сборка легковесного production-образа
├── docker-compose.yml        # Локальный запуск и монтирование volume
├── requirements.txt          # Зависимости Python
├── .env.example              # Пример файла переменных окружения
├── .env                      # Локальные переменные окружения (в .gitignore)
└── README.md
```

---

## 🚀 Быстрый старт (локально)

### 1. Клонирование и виртуальное окружение

```bash
# Перейдите в папку проекта
cd weatherparser

# Создайте и активируйте виртуальное окружение
python -m venv .venv

# Windows (PowerShell):
.\.venv\Scripts\Activate.ps1
# Linux / macOS:
source .venv/bin/activate

# Установите зависимости
pip install --upgrade pip
pip install -r requirements.txt
```

### 2. Настройка переменных окружения

Создайте файл `.env` (или используйте готовый):

```env
BOT_TOKEN=ваш_токен_бота
CITY_NAME=Санкт-Петербург
LATITUDE=59.9343
LONGITUDE=30.3351
TIMEZONE=Europe/Moscow
BROADCAST_TIME=07:00
DATABASE_URL=sqlite+aiosqlite:///./data/weather.db
```

### 3. Запуск

```bash
python -m app.main
```

---

## 🐳 Запуск через Docker Compose локально

```bash
# Сборка и запуск в фоне
docker compose up -d --build

# Просмотр логов
docker compose logs -f

# Остановка
docker compose down
```

---

## 🔄 Настройка CI/CD в GitHub Actions

Пайплайн настроен в [deploy.yml](file:///.github/workflows/deploy.yml). При каждом коммите в ветку `main` он:
1. Собирает Docker-образ и пушит его в ваш Docker Hub: `<DOCKERHUB_USERNAME>/weatherparser:latest`.
2. Подключается по SSH к вашему серверу.
3. Скачивает новый образ и перезапускает контейнер с сохранением данных базы.

### Необходимые GitHub Secrets

Перейдите в репозитории на GitHub: **Settings -> Secrets and variables -> Actions -> New repository secret** и добавьте:

| Секрет | Описание | Пример |
|---|---|---|
| `DOCKERHUB_USERNAME` | Логин на Docker Hub | `your_dockerhub_login` |
| `DOCKERHUB_TOKEN` | Access Token на Docker Hub (создается в Account Settings -> Security) | `dckr_pat_...` |
| `SERVER_HOST` | IP-адрес или домен вашего сервера | `194.87.123.45` |
| `SERVER_USER` | Пользователь на сервере | `root` или `ubuntu` |
| `SERVER_SSH_KEY` | Приватный SSH-ключ для входа на сервер | Содержимое `id_ed25519` или `id_rsa` |
| `SERVER_PORT` | Порт SSH (необязательно, по умолчанию 22) | `22` |
| `BOT_TOKEN` | Токен Telegram-бота | `8803939770:AAGVW...` |

### Подготовка сервера (один раз)

На сервере должен быть установлен Docker:
```bash
# Проверка наличия Docker
docker --version
```

Если подключаетесь по SSH ключу, убедитесь, что публичный ключ добавлен в `~/.ssh/authorized_keys` на сервере:
```bash
cat id_ed25519.pub >> ~/.ssh/authorized_keys
chmod 600 ~/.ssh/authorized_keys
```

После первого пуша в ветку `main`, GitHub Actions автоматически развернет бота в `~/weatherparser` на вашем сервере!
База данных будет сохраняться в папке `~/weatherparser/data/weather.db` и не будет сбрасываться при обновлениях.
