from typing import List
from pydantic_settings import BaseSettings, SettingsConfigDict
from pydantic import model_validator


class Settings(BaseSettings):
    bot_token: str
    database_url: str

    admin_ids: str = ""
    premium_admin_username: str = "Xamidov_xalal"

    locksmm_api_url: str = "https://locksmm.com/api/v2"
    locksmm_api_key: str = ""
    locksmm_number_api_url: str = "https://locksmm.uz"

    humo_card: str = ""
    visa_card: str = ""
    mastercard_card: str = ""
    card_owner: str = "Xamitjonov Abdulxamid"

    proof_channel_id: str = "@FastSmm_buyurtmalar"
    webhook_secret: str = ""
    webapp_url: str = ""

    default_markup_percent: float = 50

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
        case_sensitive=False,
    )

    @model_validator(mode="after")
    def normalize_database_url(self):
        if self.database_url.startswith("postgres://"):
            self.database_url = self.database_url.replace(
                "postgres://",
                "postgresql+asyncpg://",
                1,
            )
        elif self.database_url.startswith("postgresql://"):
            self.database_url = self.database_url.replace(
                "postgresql://",
                "postgresql+asyncpg://",
                1,
            )
        return self

    @property
    def admins(self) -> List[int]:
        result = []

        for raw in self.admin_ids.split(","):
            raw = raw.strip()

            if raw:
                try:
                    result.append(int(raw))
                except ValueError:
                    pass

        return result


settings = Settings()
