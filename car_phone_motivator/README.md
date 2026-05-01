# Car Phone Motivator — Voice AI Assistant MVP

Телефонный голосовой ассистент-мотиватор для водителей.  
Стек: **YandexGPT** (LLM) + **Yandex SpeechKit** (STT/TTS) + **Voximplant** (телефония) + **FastAPI** + **Docker**.

---

## Архитектура

```
Водитель (телефон)
      │  входящий звонок
      ▼
  Voximplant
  VoxEngine JS (voximplant_scenario.js)
      │  POST /call/webhook  {event: "call_started"} → greeting audio_url
      │  POST /call/audio    {call_id, audio_url}    → answer audio_url
      ▼
  FastAPI Backend
  (Docker / Yandex Serverless Container)
      │
      ├─► Yandex SpeechKit STT  →  текст реплики
      ├─► YandexGPT             →  текст ответа (1–2 предложения)
      └─► Yandex SpeechKit TTS  →  аудио ответа (OGG/Opus)
```

### Call flow (chunk-based, без стриминга)

```
1. Звонок → Voximplant → VoxEngine отвечает
   POST /call/webhook {event: "call_started"}
   ← {audio_url: <приветствие>}
   VoxEngine проигрывает приветствие, затем записывает реплику.

2. Водитель говорит → запись завершается (тишина или таймаут)
   POST /call/audio {call_id, audio_url}
   Backend: скачать запись → STT → LLM → TTS → сохранить
   ← {audio_url: <ответ>, recognized_text, answer_text}
   VoxEngine проигрывает ответ, записывает следующую реплику.

3. Цикл до завершения звонка (до 30 реплик).
```

> Ожидаемая задержка на реплику: **3–6 секунд** (STT ~0.5с + LLM ~1–3с + TTS ~0.5с + сеть).

---

## Структура проекта

```
car_phone_motivator/
  app/
    __init__.py
    config.py              # Конфигурация (pydantic-settings)
    prompts.py             # System prompt + safety triggers
    llm_yandex.py          # YandexGPT REST API
    speech_yandex.py       # SpeechKit STT + TTS
    telephony.py           # Модели Voximplant webhook
    logger.py              # Структурированное логирование метрик
    main.py                # FastAPI: все endpoints
  voximplant_scenario.js   # VoxEngine JS сценарий (загружать в Voximplant)
  Dockerfile
  requirements.txt
  .env.example
  README.md
```

---

## Переменные окружения — где и как получить

### 1. Yandex Cloud: YANDEX_API_KEY и YANDEX_FOLDER_ID

**Шаг 1. Зарегистрироваться и создать каталог**

1. Зайти на [console.yandex.cloud](https://console.yandex.cloud).
2. Создать **Каталог**: меню сверху → «Создать каталог», имя `motivator`.
3. Скопировать **ID каталога** — строка вида `b1g8s0abc123def456gh`.
   Это `YANDEX_FOLDER_ID`.

**Шаг 2. Создать сервисный аккаунт**

1. Открыть каталог → левое меню → **IAM** → **Сервисные аккаунты** → **Создать**.
2. Имя: `motivator-sa`.
3. Назначить роли (поиск по названию):
   - `ai.languageModels.user` — YandexGPT
   - `ai.speechkit.stt` — распознавание речи
   - `ai.speechkit.tts` — синтез речи
4. Нажать **Создать**.

**Шаг 3. Создать API-ключ**

1. Открыть созданный сервисный аккаунт → вкладка **API-ключи**.
2. Нажать **Создать API-ключ**, описание `motivator-key`.
3. Скопировать значение ключа (`AQVN...`) — **показывается только один раз**.
   Это `YANDEX_API_KEY`.

```bash
# Итого в .env:
YANDEX_FOLDER_ID=b1g8s0abc123def456gh
YANDEX_API_KEY=AQVNxxxxxxxxxxxxxxxxxx
```

> **Альтернатива для быстрого теста**: `yc iam create-token` → IAM-токен на 12 ч (`YANDEX_IAM_TOKEN`).

---

### 2. Voximplant: регистрация, номер, webhook

**Шаг 1. Зарегистрироваться**

1. Зайти на [voximplant.com](https://voximplant.com) → **Sign Up**.
2. Указать email, страну — Россия, подтвердить почту.
3. После входа откроется **Control Panel**.

**Шаг 2. Пополнить баланс и купить номер**

1. **Numbers** → **Buy new phone number** → Страна: Russia.
2. Выбрать номер, нажать **Buy** (~$1–2/мес.).

**Шаг 3. Создать Application**

1. **Applications** → **New Application**.
2. Имя: `motivator`. Нажать **Create**.

**Шаг 4. Загрузить VoxEngine сценарий**

1. Открыть приложение `motivator` → вкладка **Scenarios**.
2. Нажать **New scenario**, имя `motivator_scenario`.
3. Вставить содержимое файла `voximplant_scenario.js`.
4. В первой строке заменить `BACKEND_URL` на реальный URL backend:
   ```js
   var BACKEND_URL = "https://your-backend.example.com";
   ```
5. Нажать **Save**.

**Шаг 5. Создать Rule**

1. Вкладка **Routing** → **Rules** → **New Rule**.
2. Имя: `incoming`, Pattern: `.*` (все входящие).
3. Прикрепить сценарий `motivator_scenario`.
4. Нажать **Save**.

**Шаг 6. Привязать номер к Application**

1. **Numbers** → выбрать купленный номер → **Assign to Application**.
2. Выбрать приложение `motivator` → **Assign**.

**Итого**: Voximplant не требует API-ключей в `.env` — всё управление  
через VoxEngine JS, который сам обращается к нашему backend.

---

### 3. PUBLIC_BASE_URL

Публичный URL backend нужен, чтобы Voximplant мог скачать TTS-аудиофайлы.

- **Локальная разработка с ngrok:**
  ```bash
  ngrok http 8000
  # скопировать https://xxxx.ngrok-free.app
  PUBLIC_BASE_URL=https://xxxx.ngrok-free.app
  ```
  И вписать тот же URL в `BACKEND_URL` в `voximplant_scenario.js`.

- **Yandex Serverless Container:** URL выдаётся после деплоя (см. ниже).

---

## Быстрый старт (локально)

```bash
cd car_phone_motivator
cp .env.example .env
# Заполнить YANDEX_API_KEY, YANDEX_FOLDER_ID

pip install -r requirements.txt
uvicorn app.main:app --reload --port 8000
```

### Тест LLM через /chat

```bash
# Обычный запрос
curl -X POST http://localhost:8000/chat \
  -H "Content-Type: application/json" \
  -d '{"text": "Застрял в пробке уже час, нет сил"}'

# Safety-триггер — должен дать рекомендацию остановиться
curl -X POST http://localhost:8000/chat \
  -H "Content-Type: application/json" \
  -d '{"text": "Засыпаю за рулём, очень устал"}'
```

### Тест полного pipeline STT → LLM → TTS

```bash
# Нужен OGG/Opus файл с голосом (arecord, Audacity и т.п.)
curl -X POST http://localhost:8000/call/audio \
  -F "call_id=test-001" \
  -F "audio_format=oggopus" \
  -F "audio_file=@sample.ogg"
# В ответе — audio_url с готовым аудиоответом
```

### Тест webhook (симуляция Voximplant)

```bash
# Симулировать входящий звонок
curl -X POST http://localhost:8000/call/webhook \
  -H "Content-Type: application/json" \
  -d '{"event": "call_started", "call_id": "test-call-1"}'
# В ответе — audio_url приветствия
```

---

## Docker

```bash
cd car_phone_motivator

# Сборка
docker build -t car-phone-motivator .

# Запуск
docker run --env-file .env \
  -e PUBLIC_BASE_URL=http://localhost:8000 \
  -p 8000:8000 \
  car-phone-motivator

# Проверка
curl http://localhost:8000/health
```

---

## Деплой в Yandex Cloud (Serverless Container)

### Предварительные требования

```bash
# Установить Yandex Cloud CLI
curl -sSL https://storage.yandexcloud.net/yandexcloud-yc/install.sh | bash
source ~/.bashrc

# Авторизоваться (выбрать аккаунт, организацию, каталог)
yc init
```

---

### Шаг 1: Создать Container Registry и запушить образ

```bash
# Создать реестр
yc container registry create --name motivator-registry

# Получить ID реестра
REGISTRY_ID=$(yc container registry get --name motivator-registry \
  --format json | jq -r .id)

# Авторизовать Docker через yc
yc container registry configure-docker

# Собрать и запушить образ
docker build -t cr.yandex/$REGISTRY_ID/car-phone-motivator:latest .
docker push cr.yandex/$REGISTRY_ID/car-phone-motivator:latest
```

---

### Шаг 2: Сервисный аккаунт для контейнера

```bash
yc iam service-account create --name motivator-container-sa

SA_ID=$(yc iam service-account get --name motivator-container-sa \
  --format json | jq -r .id)

# Дать право тянуть образы из Registry
yc container registry add-access-binding \
  --name motivator-registry \
  --role container-registry.images.puller \
  --service-account-id $SA_ID
```

---

### Шаг 3: Создать и задеплоить Serverless Container

```bash
# Создать контейнер
yc serverless container create --name car-phone-motivator

# Задеплоить первую ревизию (подставить реальные значения)
yc serverless container revision deploy \
  --container-name car-phone-motivator \
  --image cr.yandex/$REGISTRY_ID/car-phone-motivator:latest \
  --service-account-id $SA_ID \
  --cores 1 \
  --memory 512MB \
  --concurrency 8 \
  --execution-timeout 30s \
  --environment YANDEX_API_KEY=<ваш_ключ> \
  --environment YANDEX_FOLDER_ID=<ваш_folder_id> \
  --environment SPEECHKIT_TTS_VOICE=filipp \
  --environment SPEECHKIT_TTS_SPEED=0.9 \
  --environment MAX_RECORD_SECONDS=10 \
  --environment SILENCE_TIMEOUT_SECONDS=2 \
  --environment PUBLIC_BASE_URL=https://PLACEHOLDER.containers.yandexcloud.net

# Сделать контейнер публичным (без IAM на входе)
yc serverless container allow-unauthenticated-invoke \
  --name car-phone-motivator

# Получить публичный URL
CONTAINER_URL=$(yc serverless container get \
  --name car-phone-motivator --format json | jq -r .url)

echo "Container URL: $CONTAINER_URL"
```

**После получения URL** — обновить `PUBLIC_BASE_URL` в ревизии:

```bash
yc serverless container revision deploy \
  --container-name car-phone-motivator \
  --image cr.yandex/$REGISTRY_ID/car-phone-motivator:latest \
  --service-account-id $SA_ID \
  --cores 1 --memory 512MB --concurrency 8 --execution-timeout 30s \
  --environment YANDEX_API_KEY=<ваш_ключ> \
  --environment YANDEX_FOLDER_ID=<ваш_folder_id> \
  --environment SPEECHKIT_TTS_VOICE=filipp \
  --environment SPEECHKIT_TTS_SPEED=0.9 \
  --environment MAX_RECORD_SECONDS=10 \
  --environment SILENCE_TIMEOUT_SECONDS=2 \
  --environment PUBLIC_BASE_URL=$CONTAINER_URL
```

---

### Шаг 4: Прописать URL в VoxEngine сценарии

После получения `CONTAINER_URL` открыть в Voximplant Dashboard  
сценарий `motivator_scenario` и обновить первую строку:

```js
var BACKEND_URL = "https://<CONTAINER_URL>";
```

Сохранить сценарий. Позвонить на номер — ассистент ответит.

---

### Шаг 5: Обновление (при изменениях кода)

```bash
docker build -t cr.yandex/$REGISTRY_ID/car-phone-motivator:latest .
docker push cr.yandex/$REGISTRY_ID/car-phone-motivator:latest

# Повторить команду deploy из шага 3 с теми же параметрами
```

---

## Хранилище аудио для прода (Yandex Object Storage)

По умолчанию аудио хранится в `/tmp/audio` — теряется при рестарте контейнера.  
Для прода нужен Yandex Object Storage:

```bash
# Создать бакет
yc storage bucket create --name motivator-audio

# Дать SA права
yc storage bucket update motivator-audio \
  --grants grant-type=GRANT_TYPE_ACCOUNT,permission=PERMISSION_FULL_CONTROL,grantee-id=$SA_ID
```

Заменить `_save_audio()` в `app/main.py`:

```python
import boto3, os, time

s3 = boto3.client(
    "s3",
    endpoint_url="https://storage.yandexcloud.net",
    aws_access_key_id=os.environ["S3_KEY_ID"],
    aws_secret_access_key=os.environ["S3_SECRET"],
)

def _save_audio(call_id: str, tag: str, audio_bytes: bytes) -> str:
    key = f"audio/{call_id}_{tag}_{int(time.time())}.ogg"
    s3.put_object(
        Bucket="motivator-audio", Key=key, Body=audio_bytes,
        ContentType="audio/ogg", ACL="public-read",
    )
    return f"https://storage.yandexcloud.net/motivator-audio/{key}"
```

Добавить в `requirements.txt`: `boto3==1.34.0`

---

## Endpoints

| Method | Path | Назначение |
|---|---|---|
| GET | `/health` | Проверка сервиса |
| POST | `/chat` | Тест LLM по тексту без звонка |
| POST | `/call/webhook` | Voximplant lifecycle events |
| POST | `/call/audio` | Запись реплики → ответное аудио |
| POST | `/call/respond` | Готовый текст → TTS аудиоответ |
| GET | `/audio/{filename}` | Отдача TTS-файлов (dev only) |

---

## Тестовый сценарий звонка

1. Позвонить на купленный Voximplant номер.
2. Услышать: *«Привет, я твой ассистент на дороге. Как ты сейчас?»*
3. Сказать: *«Застрял в пробке, хочется всё бросить»* → мотивирующая фраза.
4. Сказать: *«Я очень устал и засыпаю»* → рекомендация остановиться.
5. Положить трубку.

---

## Known Limitations

| # | Проблема | Решение для прода |
|---|---|---|
| 1 | Аудио в `/tmp` теряется при рестарте | Yandex Object Storage (см. выше) |
| 2 | Задержка 3–6 с на реплику | Потоковый STT (SpeechKit WebSocket) |
| 3 | Сессии в памяти (теряются при рестарте) | Yandex Managed Redis |
| 4 | Нет верификации подписи webhook | Включить `VOXIMPLANT_WEBHOOK_SECRET` + HMAC |
| 5 | `yandexgpt-lite` быстрая, но менее умная | Сменить через `YANDEXGPT_MODEL_URI=gpt://.../yandexgpt/latest` |
| 6 | VoxEngine хранит записи ограниченно | Настроить Voximplant Storage или сразу стримить аудио на backend |
