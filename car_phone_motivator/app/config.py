from pydantic_settings import BaseSettings
from functools import lru_cache


class Settings(BaseSettings):
    # Yandex Cloud
    yandex_api_key: str = ""
    yandex_folder_id: str = ""
    yandex_iam_token: str = ""  # alternative to api_key

    # YandexGPT model
    yandexgpt_model_uri: str = ""  # auto-filled from folder_id if empty

    # SpeechKit
    speechkit_tts_voice: str = "filipp"
    speechkit_tts_speed: str = "0.9"
    speechkit_stt_lang: str = "ru-RU"

    # МТС Exolve
    exolve_api_key: str = ""          # API-ключ из личного кабинета Exolve
    exolve_api_url: str = "https://api.exolve.ru"
    exolve_app_id: str = ""           # ID приложения в Exolve
    exolve_webhook_secret: str = ""   # опциональный HMAC-секрет

    # App
    app_env: str = "development"
    audio_store_path: str = "/tmp/audio"
    max_record_seconds: int = 10
    silence_timeout_seconds: int = 2

    # Публичный URL backend (без trailing slash)
    public_base_url: str = "http://localhost:8000"

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"

    @property
    def yandex_auth_header(self) -> dict:
        if self.yandex_api_key:
            return {"Authorization": f"Api-Key {self.yandex_api_key}"}
        if self.yandex_iam_token:
            return {"Authorization": f"Bearer {self.yandex_iam_token}"}
        raise ValueError("Neither YANDEX_API_KEY nor YANDEX_IAM_TOKEN is set")

    @property
    def exolve_auth_header(self) -> dict:
        return {"Authorization": f"Bearer {self.exolve_api_key}"}

    @property
    def gpt_model_uri(self) -> str:
        if self.yandexgpt_model_uri:
            return self.yandexgpt_model_uri
        return f"gpt://{self.yandex_folder_id}/yandexgpt-lite/latest"


@lru_cache
def get_settings() -> Settings:
    return Settings()
