import json
import tomllib
from pathlib import Path
from dataclasses import dataclass

from pydantic import BaseModel


@dataclass
class AuthSettings:
    """Settings for the current active user"""

    id: str
    instance_url: str
    instance_domain: str
    full_username: str
    access_token: str

    client_id: str
    client_secret: str


class Config(BaseModel):
    editor: str = "vim"


@dataclass
class Settings:
    auth: AuthSettings
    config: Config


class LoadSettingsError(Exception):
    pass


def _load_auth_settings(auth_settings_file: Path) -> AuthSettings:
    auth_settings_json = json.loads(auth_settings_file.read_text())

    full_username = auth_settings_json["current"]
    user = auth_settings_json["users"][full_username]

    user_id = user["id"]
    instance_domain = user["instance"]
    instance_url = "https://" + instance_domain
    access_token = user["access_token"]

    app = auth_settings_json["apps"][instance_domain]
    client_id = app["client_id"]
    client_secret = app["client_secret"]

    return AuthSettings(
        user_id,
        instance_url,
        instance_domain,
        full_username,
        access_token,
        client_id,
        client_secret,
    )


def create_auth_settings(auth_settings_file: Path, auth_settings: AuthSettings) -> None:
    auth_settings_file.parent.mkdir(parents=True, exist_ok=True)
    with open(auth_settings_file, "w") as f:
        auth_file_content = {
            "current": auth_settings.full_username,
            "apps": {
                auth_settings.instance_domain: {
                    "client_id": auth_settings.client_id,
                    "client_secret": auth_settings.client_secret,
                },
            },
            "users": {
                auth_settings.full_username: {
                    "id": auth_settings.id,
                    "instance": auth_settings.instance_domain,
                    "access_token": auth_settings.access_token,
                },
            },
        }
        f.write(json.dumps(auth_file_content, indent=4))


def _load_config(config_file: Path) -> Config:
    if not (config_file.exists() and config_file.is_file()):
        return Config()

    with open(config_file, "rb") as f:
        config_toml = tomllib.load(f)
    return Config.model_validate(config_toml)


def load_settings(auth_settings_file: Path, config_file: Path) -> Settings:
    if not (auth_settings_file.exists() and auth_settings_file.is_file()):
        raise LoadSettingsError(f"{auth_settings_file} does not exist!")

    auth_settings = _load_auth_settings(auth_settings_file)
    config = _load_config(config_file)
    return Settings(auth_settings, config)
