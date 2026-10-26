# Support Dispatcher

Учебный сервис для автоматического распределения заявок технической поддержки.

## Локальный запуск

Требуется Docker Engine и Docker Compose v2.

```bash
docker compose -f compose.yaml up --build -d
docker compose -f compose.yaml ps
```

Открыть http://localhost:8080 (интерфейс) или http://localhost:8080/docs (API). Логи: `docker compose -f compose.yaml logs -f api worker`. Остановить: `docker compose -f compose.yaml down`. Данные сохраняются в volumes; чтобы удалить их намеренно, используйте `docker compose -f compose.yaml down -v`.

## Категории и специалисты

Начальные специалисты создаются автоматически при первом запуске API. Навыки задаются через запятую: `network,hardware,general`. Заявки хранятся в Redis Sorted Set и обрабатываются по приоритету (1 — самый высокий), затем по id. Алгоритм выбирает активного специалиста нужной категории с минимальным количеством заявок в статусах `assigned` и `in_progress`. Если профильного специалиста нет, выбирается любой активный.

## API

- `GET /health` — состояние API, PostgreSQL и Redis.
- `GET /api/agents` — список специалистов.
- `GET /api/tickets` — список заявок.
- `POST /api/tickets` — создание заявки.
- `PATCH /api/tickets/{id}/status?status=in_progress` — изменение статуса.

## Тесты

```bash
python -m venv .venv
# Windows: .venv\\Scripts\\activate
# Linux/macOS: source .venv/bin/activate
pip install -r requirements.txt
pytest -q
```

Тесты алгоритма используют SQLite во временном файле; рабочая система использует PostgreSQL.
