# 🌤 Weather Parser Telegram Bot

Асинхронный Telegram-бот прогноза погоды с возможностью выбора любого города мира, автоматической рассылкой в **07:00 по местному времени пользователя**, защитой от лимитов (дедупликация и кэширование), базой данных подписчиков на **SQLite + SQLAlchemy (async)**, контейнеризацией в **Docker** и **CI/CD в GitHub Actions**.

---

## 📋 Возможности

* 🌍 **Свободный выбор города**:
  * Поиск любого города мира через Open-Meteo Geocoding API.
  * Инлайн-кнопки для разрешения неоднозначностей (например: Ростов-на-Дону vs Ростов Великий).
  * Поддержка отправки геолокации 📎 с автоматическим определением города.
* ⏰ **Персональная утренняя рассылка в 07:00**: бот определяет часовой пояс города и доставляет прогноз ровно в 7 утра по местному времени пользователя.
* 📊 **Компактная сводка на день**:
  * Температура и «ощущается как» для **Утра**, **Дня** и **Вечера**.
  * Описание погоды и эмодзи.
  * Осадки с расчетом точного временного интервала (например, `дождь до 2.1 мм (08:00–12:00)`).
  * Ветер (скорость, порывы и текстовая категория).
* 💬 **Интерактивные команды**:
  * `/start` — начало работы и настройка города.
  * `/city` — выбрать или изменить город (например, `/city Казань`).
  * `/weather` — получить свежий прогноз прямо сейчас.
  * `/stop` — отключить утреннюю рассылку.
  * `/help` — список команд и текущий выбранный город.
* 🛡 **Отказоустойчивость и масштабируемость (1000+ пользователей)**:
  * Дедупликация запросов погоды по городам (для 100 пользователей из одного города делается 1 запрос к API, защищая от 429 ошибки).
  * Retry-механизм (до 3 попыток с нарастающей паузой) для защиты от временных сбоев API (HTTP 503).
  * Автоматическое выявление и отписка пользователей, заблокировавших бота, без сбоя рассылки.
  * Паузы между отправками сообщений (`0.04s`) для соблюдения Telegram Flood Control.
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
