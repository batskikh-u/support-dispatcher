# Support Dispatcher

Учебный сервис для автоматического распределения заявок технической поддержки.
Пять контейнеров: `web` (nginx), `api` (FastAPI), `worker`, `db` (PostgreSQL), `redis`.

## Структура проекта

```
app/                  # backend: API и фоновый обработчик (Python-пакет)
frontend/             # веб-интерфейс, nginx.conf и Dockerfile контейнера web
tests/                # автоматические тесты (pytest)
scripts/smoke_test.sh # проверка системы после развёртывания
.github/workflows/    # конвейер CI/CD (GitHub Actions)
Dockerfile            # образ api и worker
compose.yaml          # запуск на одном узле (Docker Compose)
compose.swarm.yaml    # развёртывание в кластере Docker Swarm
pytest.ini  requirements.txt  .env.example  .dockerignore
```

## Запуск в Docker Compose

Требуется Docker Engine и Docker Compose v2.

```bash
cp .env.example .env
docker compose -f compose.yaml up --build -d
docker compose -f compose.yaml ps
```

Интерфейс: http://localhost:8080, документация API: http://localhost:8080/docs.
Логи: `docker compose -f compose.yaml logs -f api worker`.
Остановка: `docker compose -f compose.yaml down`
(`down -v` дополнительно удаляет тома с данными).

## Тесты

Нужен **Python 3.10 или новее** (в коде используется синтаксис `int | None`; в Docker-образе — 3.12).
Команды выполняются из корня проекта (там, где лежат `pytest.ini` и папка `app`).

```bash
python -m venv .venv
# Windows (PowerShell):  .venv\Scripts\Activate.ps1
# Linux/macOS:           source .venv/bin/activate
pip install -r requirements.txt
python -m pytest -q
```

Ожидается 23 пройденных теста: 10 модульных (`tests/test_assignment.py`) и 13 тестов API (`tests/test_api.py`).
Тесты используют SQLite во временном каталоге и заглушку вместо Redis, поэтому Docker и запущенные
контейнеры для них не нужны. Рабочая система использует PostgreSQL и Redis.

Если тесты не проходят, сначала проверьте:

1. `python --version` — не ниже 3.10;
2. тесты запускаются из корня проекта, а в `app/` лежит файл `__init__.py`;
3. зависимости установлены именно в активное виртуальное окружение (`pip list | grep -i -E "fastapi|sqlalchemy|pytest|httpx"`);
4. в окружении не заданы переменные `DATABASE_URL` и `REDIS_URL`, указывающие на реальные сервисы
   (тесты задают свои значения сами, но удобнее их сбросить).

## Кластер Docker Swarm

```bash
docker swarm init --advertise-addr <IP менеджера>          # на manager
docker swarm join --token <TOKEN> <IP менеджера>:2377        # на worker
export REGISTRY_IMAGE=ghcr.io/<владелец>/<репозиторий> IMAGE_TAG=latest POSTGRES_PASSWORD=<пароль>
docker stack deploy --with-registry-auth -c compose.swarm.yaml support
docker stack services support
```

`docker stack deploy` не читает файл `.env`: переменные берутся из окружения оболочки.

## CI/CD

Конвейер `.github/workflows/ci-cd.yml`: тесты → сборка и публикация образов в GHCR → деплой в Swarm по SSH →
проверка `scripts/smoke_test.sh` с автоматическим откатом. Секреты репозитория: `DEPLOY_HOST`, `DEPLOY_USER`,
`SSH_PRIVATE_KEY`. Пароль БД хранится на сервере в `/opt/support/.env`.

## API

- `GET /health` — состояние API, PostgreSQL и Redis.
- `GET /api/agents` — список специалистов.
- `GET /api/tickets` — список заявок.
- `POST /api/tickets` — создание заявки.
- `PATCH /api/tickets/{id}/status?status=in_progress` — изменение статуса.

## Алгоритм

Заявки лежат в Redis Sorted Set; оценка = `приоритет · 10^9 + id`, первой извлекается наименьшая.
Исполнитель: активный специалист с нужной категорией в навыках (если таких нет — любой активный) с минимальным
числом заявок в статусах `assigned` и `in_progress`; при равенстве — с меньшим id.
