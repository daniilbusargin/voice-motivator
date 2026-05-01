# Car Phone Motivator — Voice AI Assistant MVP

Телефонный голосовой ассистент-мотиватор для водителей.  
Стек: **YandexGPT** (LLM) + **Yandex SpeechKit** (STT/TTS) + **МТС Exolve** (телефония) + **FastAPI** + **Docker**.

---

## Архитектура

```
Водитель (телефон)
      │  входящий звонок
      ▼
  МТС Exolve
  (телефонная платформа)
      │  POST /call/webhook  {EventType: "OnCallStart"}
      │  POST /call/webhook  {EventType: "OnRecordFinish", RecordURL: "..."}
      ▼
  FastAPI Backend
  (Docker / Yandex Serverless Container)
      │
      ├─► Yandex SpeechKit STT  →  текст реплики
      ├─► YandexGPT             →  текст ответа
      └─► Yandex SpeechKit TTS  →  аудио ответа (OGG/Opus)
      │
      └── возвращает Exolve команды: PlayAudio + StartRecord
```

### Call flow (chunk-based, без стриминга)

```
1. Звонок → Exolve → POST /call/webhook (OnCallStart)
   Backend: TTS(приветствие) → URL
   Ответ: {Commands: [PlayAudio(url), StartRecord(10s)]}

2. Водитель говорит → Exolve записывает → POST /call/webhook (OnRecordFinish)
   Backend: скачать запись → STT → LLM → TTS → URL
   Ответ: {Commands: [PlayAudio(url), StartRecord(10s)]}

3. Цикл продолжается до завершения звонка.
```

> Ожидаемая суммарная задержка на реплику: **3–6 секунд** (STT ~0.5s + LLM ~1–3s + TTS ~0.5s + сеть).

---

## Структура проекта

```
car_phone_motivator/
  app/
    __init__.py
    config.py          # Конфигурация (pydantic-settings)
    prompts.py         # System prompt + safety triggers
    llm_yandex.py      # YandexGPT REST API
    speech_yandex.py   # SpeechKit STT + TTS
    telephony.py       # Модели и команды Exolve
    logger.py          # Структурированное логирование метрик
    main.py            # FastAPI: все endpoints
  Dockerfile
  requirements.txt
  .env.example
  README.md  ← этот файл
```

---

## Переменные окружения — где и как получить

### 1. Yandex Cloud: YANDEX_API_KEY и YANDEX_FOLDER_ID

**Шаг 1. Зарегистрироваться и создать каталог**

1. Зайти на [console.yandex.cloud](https://console.yandex.cloud).
2. Если нет организации — создать её (бесплатно).
3. Создать **Каталог** (Folder): любое имя, например `motivator`.
4. Скопировать **ID каталога** — строка вида `b1g8s0abc123def456gh`.  
   Это и есть `YANDEX_FOLDER_ID`.

**Шаг 2. Создать сервисный аккаунт**

1. В каталоге → **IAM** → **Сервисные аккаунты** → **Создать**.
2. Имя: `motivator-sa`.
3. Назначить роли:
   - `ai.languageModels.user` — для YandexGPT
   - `ai.speechkit.stt` — для распознавания речи
   - `ai.speechkit.tts` — для синтеза речи
4. Нажать **Создать**.

**Шаг 3. Создать API-ключ**

1. Открыть созданный сервисный аккаунт.
2. Вкладка **API-ключи** → **Создать API-ключ**.
3. Описание: `motivator-key`.
4. Скопировать значение ключа (`AQVN...`) — **показывается только один раз**.  
   Это и есть `YANDEX_API_KEY`.

**Итого:**
```
YANDEX_FOLDER_ID=b1g8s0abc123def456gh   # из шага 1
YANDEX_API_KEY=AQVNxxxxxxxxxxxxxxxxxx   # из шага 3
```

> **Альтернатива для теста**: `yc iam create-token` → даёт IAM-токен на 12 ч (`YANDEX_IAM_TOKEN`).

---

### 2. МТС Exolve: EXOLVE_API_KEY и EXOLVE_APP_ID

**Шаг 1. Зарегистрироваться**

1. Зайти на [exolve.ru](https://exolve.ru).
2. Нажать **Подключиться** → заполнить форму (email, телефон, компания).
3. После подтверждения email войти в личный кабинет.

**Шаг 2. Пополнить баланс**

Для покупки номера нужен положительный баланс.  
Раздел **Финансы** → **Пополнить** (минимум ~300 ₽).

**Шаг 3. Купить телефонный номер**

1. Раздел **Номера** → **Подключить номер**.
2. Выбрать регион (Москва / Федеральный 8-800).
3. Подтвердить покупку (~от 30–100 ₽/мес.).

**Шаг 4. Создать приложение**

1. Раздел **Приложения** → **Создать приложение**.
2. Тип: **VoiceBot** (или "Голосовой бот").
3. Имя: `motivator`.
4. **Webhook URL** → вставить URL вашего backend + `/call/webhook`:  
   `https://your-backend.example.com/call/webhook`
5. Сохранить приложение.
6. Скопировать **ID приложения** → `EXOLVE_APP_ID`.

**Шаг 5. Получить API-ключ**

1. Раздел **Настройки** → **API** → **Создать ключ**.
2. Скопировать ключ → `EXOLVE_API_KEY`.

**Шаг 6. Привязать номер к приложению**

1. Раздел **Номера** → выбрать купленный номер.
2. Привязать к приложению `motivator`.

**Итого:**
```
EXOLVE_API_KEY=eyJhbGci...        # из шага 5
EXOLVE_APP_ID=app-uuid-1234       # из шага 4
```

---

### 3. PUBLIC_BASE_URL

Это публичный URL вашего backend — нужен, чтобы Exolve мог скачать  
аудиофайлы ответов ассистента.

- **Локальная разработка с ngrok:**
  ```bash
  ngrok http 8000
  # скопировать https://xxxx.ngrok-free.app
  PUBLIC_BASE_URL=https://xxxx.ngrok-free.app
  ```
- **Yandex Serverless Container:** URL выдаётся после деплоя (см. ниже).

---

## Быстрый старт (локально)

```bash
cd car_phone_motivator
cp .env.example .env
# Заполнить YANDEX_API_KEY, YANDEX_FOLDER_ID, EXOLVE_API_KEY, EXOLVE_APP_ID

pip install -r requirements.txt
uvicorn app.main:app --reload --port 8000
```

### Тест LLM через /chat

```bash
# Обычный запрос мотивации
curl -X POST http://localhost:8000/chat \
  -H "Content-Type: application/json" \
  -d '{"text": "Застрял в пробке, уже час стою"}'

# Проверка safety-триггера (должен дать рекомендацию остановиться)
curl -X POST http://localhost:8000/chat \
  -H "Content-Type: application/json" \
  -d '{"text": "Я очень устал и засыпаю за рулём"}'
```

Ожидаемый ответ:
```json
{
  "call_id": "...",
  "answer": "Пожалуйста, снизь скорость и держи дистанцию. При первой возможности безопасно остановись и отдохни.",
  "latency_llm_ms": 0
}
```

### Тест полного pipeline (STT → LLM → TTS)

```bash
# Нужен OGG/Opus файл с голосом (можно записать через Audacity или arecord)
curl -X POST http://localhost:8000/call/audio \
  -F "call_id=test-001" \
  -F "audio_format=oggopus" \
  -F "audio_file=@sample.ogg"
# В ответе — audio_url с готовым аудиоответом
```

---

## Docker

```bash
# Сборка
cd car_phone_motivator
docker build -t car-phone-motivator .

# Запуск локально
docker run --env-file .env \
  -e PUBLIC_BASE_URL=http://localhost:8000 \
  -p 8000:8000 \
  car-phone-motivator

# Проверка
curl http://localhost:8000/health
```

---

## Деплой в Yandex Cloud

### Предварительные требования

Установить и настроить Yandex Cloud CLI:
```bash
# Установка
curl -sSL https://storage.yandexcloud.net/yandexcloud-yc/install.sh | bash
source ~/.bashrc

# Авторизация
yc init
# Выбрать аккаунт, организацию и каталог (тот же YANDEX_FOLDER_ID)
```

---

### Шаг 1: Container Registry — создать реестр и запушить образ

```bash
# Создать реестр (один раз)
yc container registry create --name motivator-registry --folder-id $YANDEX_FOLDER_ID

# Получить ID реестра
REGISTRY_ID=$(yc container registry get --name motivator-registry \
  --folder-id $YANDEX_FOLDER_ID --format json | jq -r .id)

echo "Registry ID: $REGISTRY_ID"

# Настроить Docker для авторизации через yc
yc container registry configure-docker

# Собрать и запушить образ
docker build -t cr.yandex/$REGISTRY_ID/car-phone-motivator:latest .
docker push cr.yandex/$REGISTRY_ID/car-phone-motivator:latest
```

---

### Шаг 2: Сервисный аккаунт для контейнера

```bash
# Создать SA для Serverless Container (если ещё не создан)
yc iam service-account create \
  --name motivator-container-sa \
  --folder-id $YANDEX_FOLDER_ID

SA_ID=$(yc iam service-account get --name motivator-container-sa \
  --folder-id $YANDEX_FOLDER_ID --format json | jq -r .id)

# Дать SA право тянуть образы из Registry
yc container registry add-access-binding \
  --name motivator-registry \
  --role container-registry.images.puller \
  --service-account-id $SA_ID
```

---

### Шаг 3: Создать Serverless Container

```bash
# Создать контейнер
yc serverless container create \
  --name car-phone-motivator \
  --folder-id $YANDEX_FOLDER_ID

# Задеплоить ревизию (подставить реальные значения переменных)
yc serverless container revision deploy \
  --container-name car-phone-motivator \
  --folder-id $YANDEX_FOLDER_ID \
  --image cr.yandex/$REGISTRY_ID/car-phone-motivator:latest \
  --service-account-id $SA_ID \
  --cores 1 \
  --memory 512MB \
  --concurrency 8 \
  --execution-timeout 30s \
  --environment YANDEX_API_KEY=<ваш_ключ> \
  --environment YANDEX_FOLDER_ID=<ваш_folder_id> \
  --environment EXOLVE_API_KEY=<ваш_exolve_ключ> \
  --environment EXOLVE_APP_ID=<ваш_exolve_app_id> \
  --environment SPEECHKIT_TTS_VOICE=filipp \
  --environment SPEECHKIT_TTS_SPEED=0.9 \
  --environment MAX_RECORD_SECONDS=10 \
  --environment SILENCE_TIMEOUT_SECONDS=2 \
  --environment PUBLIC_BASE_URL=https://PLACEHOLDER.containers.yandexcloud.net

# Сделать контейнер публично доступным (без IAM-токена на входе)
yc serverless container allow-unauthenticated-invoke \
  --name car-phone-motivator \
  --folder-id $YANDEX_FOLDER_ID

# Получить публичный URL контейнера
CONTAINER_URL=$(yc serverless container get \
  --name car-phone-motivator \
  --folder-id $YANDEX_FOLDER_ID \
  --format json | jq -r .url)

echo "Container URL: $CONTAINER_URL"
```

**Важно**: после получения `CONTAINER_URL` обновить переменную `PUBLIC_BASE_URL`  
в ревизии контейнера:
```bash
yc serverless container revision deploy \
  --container-name car-phone-motivator \
  --folder-id $YANDEX_FOLDER_ID \
  --image cr.yandex/$REGISTRY_ID/car-phone-motivator:latest \
  --service-account-id $SA_ID \
  --cores 1 --memory 512MB --concurrency 8 --execution-timeout 30s \
  --environment PUBLIC_BASE_URL=$CONTAINER_URL \
  # ... остальные переменные те же
```

---

### Шаг 4: Прописать webhook URL в Exolve

После получения `CONTAINER_URL`:

1. Зайти в [lk.exolve.ru](https://lk.exolve.ru) → **Приложения** → выбрать `motivator`.
2. В поле **Webhook URL** указать:
   ```
   https://<CONTAINER_URL>/call/webhook
   ```
3. Сохранить.

**Проверить деплой:**
```bash
curl https://$CONTAINER_URL/health
# → {"status": "ok", "service": "car_phone_motivator"}
```

---

### Шаг 5: Обновление (при изменениях кода)

```bash
# Пересобрать и запушить образ
docker build -t cr.yandex/$REGISTRY_ID/car-phone-motivator:latest .
docker push cr.yandex/$REGISTRY_ID/car-phone-motivator:latest

# Задеплоить новую ревизию (команда из шага 3 повторяется)
yc serverless container revision deploy \
  --container-name car-phone-motivator \
  ...
```

---

## Настройка хранилища аудио для прода (Yandex Object Storage)

По умолчанию аудиофайлы хранятся в `/tmp/audio` внутри контейнера — они  
теряются при перезапуске. Для прода нужен Yandex Object Storage:

```bash
# Создать бакет
yc storage bucket create --name motivator-audio --folder-id $YANDEX_FOLDER_ID

# Дать SA права на запись
yc storage bucket update motivator-audio \
  --grants grant-type=GRANT_TYPE_ACCOUNT,permission=PERMISSION_FULL_CONTROL,grantee-id=$SA_ID
```

Затем в `app/main.py` функцию `_save_audio()` заменить на загрузку в S3:

```python
import boto3, os

s3 = boto3.client(
    "s3",
    endpoint_url="https://storage.yandexcloud.net",
    aws_access_key_id=os.environ["S3_KEY_ID"],
    aws_secret_access_key=os.environ["S3_SECRET"],
)

def _save_audio(call_id: str, tag: str, audio_bytes: bytes) -> str:
    key = f"audio/{call_id}_{tag}_{int(time.time())}.ogg"
    s3.put_object(Bucket="motivator-audio", Key=key, Body=audio_bytes,
                  ContentType="audio/ogg", ACL="public-read")
    return f"https://storage.yandexcloud.net/motivator-audio/{key}"
```

Добавить в `requirements.txt`: `boto3==1.34.0`

---

## Тестовый сценарий звонка

1. Позвонить на купленный Exolve номер.
2. Услышать: *«Привет, я твой ассистент на дороге. Как ты сейчас?»*
3. Сказать: *«Застрял в пробке, хочется всё бросить»* → услышать мотивирующую фразу.
4. Сказать: *«Я устал и хочу спать»* → услышать рекомендацию остановиться.
5. Положить трубку.

---

## Endpoints

| Method | Path | Назначение |
|---|---|---|
| GET | `/health` | Проверка сервиса |
| POST | `/chat` | Тест LLM по тексту без звонка |
| POST | `/call/webhook` | Exolve lifecycle events (основной endpoint) |
| POST | `/call/audio` | Тест pipeline с аудиофайлом (curl/Postman) |
| POST | `/call/respond` | Готовый текст → TTS аудиоответ |
| GET | `/audio/{filename}` | Отдача TTS-файлов (dev only) |

---

## Known Limitations

| # | Проблема | Решение для прода |
|---|---|---|
| 1 | Аудио в `/tmp` теряется при рестарте | Yandex Object Storage (см. выше) |
| 2 | Задержка 3–6 с на реплику | Потоковый STT (SpeechKit WebSocket) |
| 3 | Сессии в памяти (теряются при рестарте) | Yandex Managed Redis |
| 4 | Нет верификации webhook-подписи | Включить `EXOLVE_WEBHOOK_SECRET` + HMAC |
| 5 | SpeechKit отдаёт OGG, Exolve ждёт OGG — OK, но формат записи Exolve нужно уточнить | Проверить `audio_format` в документации Exolve |
| 6 | `yandexgpt-lite` — быстрая, но менее умная модель | Сменить на `yandexgpt/latest` через `YANDEXGPT_MODEL_URI` |
