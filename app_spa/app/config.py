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
settings = Settings()
