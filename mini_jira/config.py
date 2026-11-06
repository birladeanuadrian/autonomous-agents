from pydantic import SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    database_url: SecretStr = SecretStr(
        "postgresql+psycopg://mini_jira:mini_jira_local@127.0.0.1:5432/mini_jira"
    )
    test_database_url: SecretStr = SecretStr(
        "postgresql+psycopg://mini_jira:mini_jira_local@127.0.0.1:5433/mini_jira_test"
    )
