from dataclasses import dataclass
from pathlib import Path

import tomllib
from pydantic import BaseModel

from fediboat.entities import NotificationTypeEnum


class AppSettings(BaseModel):
    client_id: str
    client_secret: str


class UserSettings(BaseModel):
    id: str
    instance: str
    access_token: str


class AuthSettingsJson(BaseModel):
    """Used to validate json file structure"""

    current: str
    apps: dict[str, AppSettings]
    users: dict[str, UserSettings]


class AuthSettings(BaseModel):
    """Settings for the current active user"""

    id: str
    instance_url: str
    instance_domain: str
    full_username: str
    access_token: str

    client_id: str
    client_secret: str


class NotificationsConfig(BaseModel):
    show: list[NotificationTypeEnum] = [
        NotificationTypeEnum.favourite,
        NotificationTypeEnum.mention,
        NotificationTypeEnum.reblog,
        NotificationTypeEnum.follow,
    ]
    signs: dict[NotificationTypeEnum, tuple[str, str]] = {}


class Config(BaseModel):
    editor: str = "vim"
    notifications: NotificationsConfig = NotificationsConfig()


@dataclass
class Settings:
    auth: AuthSettings
    config: Config


class LoadSettingsError(Exception):
    pass


def _load_auth_settings(auth_settings_file: Path) -> AuthSettings:
    auth_settings_raw_json = auth_settings_file.read_text()
    auth_settings_json = AuthSettingsJson.model_validate_json(auth_settings_raw_json)

    user_data = auth_settings_json.users[auth_settings_json.current]
    app = auth_settings_json.apps[user_data.instance]
    instance_url = "https://" + user_data.instance

    return AuthSettings(
        id=user_data.id,
        instance_url=instance_url,
        instance_domain=user_data.instance,
        full_username=auth_settings_json.current,
        access_token=user_data.access_token,
        client_id=app.client_id,
        client_secret=app.client_secret,
    )


def create_auth_settings(auth_settings_file: Path, auth_settings: AuthSettings) -> None:
    auth_settings_file.parent.mkdir(parents=True, exist_ok=True)
    auth_settings_json = AuthSettingsJson(
        current=auth_settings.full_username,
        apps={
            auth_settings.instance_domain: AppSettings(
                client_id=auth_settings.client_id,
                client_secret=auth_settings.client_secret,
            ),
        },
        users={
            auth_settings.full_username: UserSettings(
                id=auth_settings.id,
                instance=auth_settings.instance_domain,
                access_token=auth_settings.access_token,
            ),
        },
    )
    auth_settings_raw_json = auth_settings_json.model_dump_json(indent=4)
    auth_settings_file.write_text(auth_settings_raw_json)


def _load_config(config_file: Path) -> Config:
    if not (config_file.exists() and config_file.is_file()):
        return Config()

    with open(config_file, "rb") as f:
        config_toml = tomllib.load(f)
    config = Config.model_validate(config_toml)
    default_signs: dict[NotificationTypeEnum, tuple[str, str]] = {
        NotificationTypeEnum.favourite: ("★", "#FFD32C"),
        NotificationTypeEnum.mention: ("@", "#82C8E5"),
        NotificationTypeEnum.reblog: ("⮂", "#79BD9A"),
        NotificationTypeEnum.follow: ("+", ""),
        NotificationTypeEnum.follow_request: ("r", ""),
        NotificationTypeEnum.moderation_warning: ("w", "#C04657"),
    }

    config.notifications.signs = {**default_signs, **config.notifications.signs}
    return config


def load_settings(auth_settings_file: Path, config_file: Path) -> Settings:
    if not (auth_settings_file.exists() and auth_settings_file.is_file()):
        raise LoadSettingsError(f"{auth_settings_file} does not exist!")

    auth_settings = _load_auth_settings(auth_settings_file)
    config = _load_config(config_file)
    return Settings(auth_settings, config)
