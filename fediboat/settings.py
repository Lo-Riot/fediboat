import json
from pathlib import Path
from dataclasses import dataclass


@dataclass
class AuthSettings:
    """Settings for the current active user"""

    instance_url: str
    instance_domain: str
    full_username: str
    access_token: str

    client_id: str
    client_secret: str


@dataclass
class Settings:
    auth: AuthSettings


class LoadSettingsError(Exception):
    pass


def load_settings(auth_settings_file: Path) -> Settings:
    if not (auth_settings_file.exists() and auth_settings_file.is_file()):
        raise LoadSettingsError(f"{auth_settings_file} does not exist!")

    auth_settings_json = json.loads(auth_settings_file.read_text())
    current_user = auth_settings_json["current"]
    instance_domain = auth_settings_json["current"].split("@")[1]
    instance_url = "https://" + instance_domain

    access_token = auth_settings_json["users"][current_user]["access_token"]
    client_id = auth_settings_json["apps"][instance_domain]["client_id"]
    client_secret = auth_settings_json["apps"][instance_domain]["client_secret"]

    auth_settings = AuthSettings(
        instance_url,
        instance_domain,
        current_user,
        access_token,
        client_id,
        client_secret,
    )
    return Settings(auth_settings)


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
                    "access_token": auth_settings.access_token,
                },
            },
        }
        f.write(json.dumps(auth_file_content))
