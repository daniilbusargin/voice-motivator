# Car Phone Motivator — Voice AI Assistant MVP

Телефонный голосовой ассистент-мотиватор для водителей.
Работает на базе YandexGPT + Yandex SpeechKit + Voximplant.

---

## Архитектура

```
Водитель (телефон)
      │ звонок
      ▼
  Voximplant
  VoxEngine JS
      │  POST /call/webhook   (событие call_started → greeting audio)
      │  POST /call/audio     (аудио реплики → ответное аудио)
      ▼
  FastAPI Backend  (Docker / Yandex Serverless Container)
      │
      ├─► Yandex SpeechKit STT  →  текст реплики
      ├─► YandexGPT              →  текст ответа
      └─► Yandex SpeechKit TTS  →  аудио ответа (OGG/Opus)
```

### Call flow (chunk-based)
1. Входящий звонок → Voximplant отвечает.  
2. Backend возвращает приветственное аудио → VoxEngine проигрывает.  
3. VoxEngine записывает реплику водителя (до 8 с или до паузы).  
4. `POST /call/audio` с URL записи → STT → LLM → TTS → URL ответного аудио.  
5. VoxEngine проигрывает ответ → снова пишет. Цикл продолжается.

---

## Переменные окружения

Скопируй `.env.example` → `.env` и заполни:

| Переменная | Обязательна | Описание |
|---|---|---|
| `YANDEX_API_KEY` | ✅ | Сервисный ключ IAM (Yandex Cloud) |
| `YANDEX_FOLDER_ID` | ✅ | ID каталога в Yandex Cloud |
| `YANDEX_IAM_TOKEN` | — | Альтернатива API-ключу (14 ч TTL) |
| `YANDEXGPT_MODEL_URI` | — | Переопределить модель GPT |
| `SPEECHKIT_TTS_VOICE` | — | Голос TTS (по умолч. `filipp`) |
| `SPEECHKIT_TTS_SPEED` | — | Скорость речи 0.1–3.0 (по умолч. `0.9`) |
| `PUBLIC_BASE_URL` | ✅ | Публичный URL backend без `/` в конце |
| `VOXIMPLANT_WEBHOOK_SECRET` | — | HMAC-секрет для проверки webhook |

---

## Быстрый старт (локально)

```bash
cd car_phone_motivator
cp .env.example .env
# заполни .env

# Установить зависимости
pip install -r requirements.txt

# Запуск
uvicorn app.main:app --reload --port 8000

# Smoke-test LLM
curl -X POST http://localhost:8000/chat \
  -H "Content-Type: application/json" \
  -d '{"text": "Устал, хочется спать за рулём"}'
```

Ожидаемый ответ:
```json
{
  "call_id": "...",
  "answer": "Пожалуйста, снизь скорость и держи дистанцию. При первой возможности безопасно остановись и отдохни.",
  "latency_llm_ms": 0
}
```

---

## Docker

```bash
# Сборка
docker build -t car-phone-motivator .

# Локальный запуск
docker run --env-file .env \
  -e PUBLIC_BASE_URL=http://localhost:8000 \
  -p 8000:8000 \
  car-phone-motivator

# Проверка
curl http://localhost:8000/health
```

---

## Деплой в Yandex Serverless Container

### 1. Подготовить Container Registry

```bash
# Создать реестр (один раз)
yc container registry create --name motivator-registry

# Аутентификация Docker
yc container registry configure-docker

REGISTRY_ID=$(yc container registry get --name motivator-registry --format json | jq -r .id)
```

### 2. Собрать и запушить образ

```bash
docker build -t cr.yandex/$REGISTRY_ID/car-phone-motivator:latest .
docker push cr.yandex/$REGISTRY_ID/car-phone-motivator:latest
```

### 3. Создать Serverless Container

```bash
yc serverless container create --name car-phone-motivator

yc serverless container revision deploy \
  --container-name car-phone-motivator \
  --image cr.yandex/$REGISTRY_ID/car-phone-motivator:latest \
  --cores 1 \
  --memory 512MB \
  --concurrency 4 \
  --execution-timeout 30s \
  --environment YANDEX_API_KEY=<key> \
  --environment YANDEX_FOLDER_ID=<folder_id> \
  --environment PUBLIC_BASE_URL=https://<container_id>.containers.yandexcloud.net \
  --service-account-id <sa_id>

# Сделать публичным (без IAM на входе)
yc serverless container allow-unauthenticated-invoke --name car-phone-motivator

# Получить публичный URL
yc serverless container get --name car-phone-motivator --format json | jq -r .url
```

> **Важно**: для хранения аудиофайлов в проде замени `_save_audio()` в `main.py`
> на загрузку в Yandex Object Storage (boto3 / yandex-s3) и возвращай публичный S3-URL.

---

## Настройка Voximplant

### 1. Зарегистрировать аккаунт и купить номер

1. Зарегистрироваться на [voximplant.com](https://voximplant.com).
2. В разделе **Numbers** арендовать российский номер (+7...).
3. Создать **Application** → дать имя `motivator`.

### 2. Загрузить сценарий

1. В приложении перейти в **Scenarios**.
2. Создать новый сценарий, вставить содержимое `voximplant_scenario.js`.
3. В первой строке сценария заменить `BACKEND_URL` на публичный URL backend.
4. Сохранить сценарий.

### 3. Создать Rule

1. В приложении → **Routing** → **Rules** → New Rule.
2. Pattern: `.*` (все входящие звонки).
3. Прикрепить созданный сценарий.
4. Привязать купленный номер к этому Application.

### 4. Тестовый звонок

Позвони на купленный номер — ассистент ответит приветствием и начнёт диалог.

---

## Endpoints

| Method | Path | Описание |
|---|---|---|
| GET | `/health` | Проверка сервиса |
| POST | `/chat` | Тест LLM без звонка |
| POST | `/call/webhook` | Voximplant lifecycle events |
| POST | `/call/audio` | Аудио реплики → ответное аудио |
| POST | `/call/respond` | Готовый текст → ответное аудио |
| GET | `/audio/{filename}` | Отдача аудиофайла (dev only) |

### POST /chat — пример

```bash
curl -X POST https://<your-url>/chat \
  -H "Content-Type: application/json" \
  -d '{"text": "Мне нужна мотивация, застрял в пробке"}'
```

### POST /call/audio — пример

```bash
curl -X POST https://<your-url>/call/audio \
  -F "call_id=test-001" \
  -F "audio_format=oggopus" \
  -F "audio_file=@sample.ogg"
```

---

## Known Limitations

1. **Аудио хранится локально** `/tmp/audio` — не персистентно в Serverless Container.
   В проде нужен Yandex Object Storage с публичным доступом на чтение.

2. **Без стриминга** — chunk-based latency ~3–6 с (STT + LLM + TTS).
   Для снижения задержки: потоковый STT через WebSocket SpeechKit + streaming GPT.

3. **Нет аутентификации webhook** — в проде включи `VOXIMPLANT_WEBHOOK_SECRET`
   и добавь проверку HMAC-подписи в `call_webhook`.

4. **Сессии в памяти** — при перезапуске контейнера теряются.
   Для prod: Redis или Yandex Managed Redis.

5. **Voximplant хранит записи** — нужен платный тариф или настройка Storage.
   Альтернатива: использовать Voximplant ASR (но тогда STT не через SpeechKit).

6. **IAM-токен** протухает через 12 ч. Используй API-ключ (`YANDEX_API_KEY`).
