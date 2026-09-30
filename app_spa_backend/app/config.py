from pydantic_settings import BaseSettings, SettingsConfigDict

class Settings(BaseSettings):
	model_config = SettingsConfigDict(env_file=".env", extra="ignore")

	postgres_user: str
	postgres_password: str
	postgres_db: str
	postgres_host: str = "db"
	postgres_port: int = 5432
	database_url: str
	api_port: int = 8000

	#LLM
	llm_api_key: str = ""
	llm_base_url: str = "https://ai.api.cloud.yandex.net/v1"
	llm_model: str = ""
	llm_folder_id: str = ""

settings = Settings()
