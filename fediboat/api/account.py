import requests
import webbrowser

from fediboat.settings import AuthSettings


class APIError(Exception):
    pass


class LoginError(APIError):
    pass


class AppCreateError(APIError):
    pass


def _get_headers(access_token: str):
    return {"Authorization": f"Bearer {access_token}"}


def create_app(instance_url: str) -> dict:
    return requests.post(
        f"{instance_url}/api/v1/apps",
        data={
            "client_name": "Fediboat",
            "redirect_uris": "urn:ietf:wg:oauth:2.0:oob",
            "scopes": "read write follow",
            "website": "https://github.com/Lo-Riot/fediboat",
        },
    ).json()


def auth(instance_url: str, client_id: int, client_secret: str, authz_code: str) -> str:
    resp = requests.post(
        f"{instance_url}/oauth/token",
        data={
            "client_id": client_id,
            "client_secret": client_secret,
            "redirect_uri": "urn:ietf:wg:oauth:2.0:oob",
            "grant_type": "authorization_code",
            "code": authz_code,
            "scope": "read write follow",
        },
    ).json()
    return resp["access_token"]


def verify_credentials(instance_url: str, access_token: str) -> dict:
    """Returns account id or raises LoginError"""
    resp = requests.get(
        f"{instance_url}/api/v1/accounts/verify_credentials",
        headers=_get_headers(access_token),
    )
    resp_data = resp.json()

    if resp.status_code != 200:
        raise LoginError(resp_data["error"])
    return resp_data


class AccountAPI:
    """API for a logged in account"""

    def __init__(self, settings: AuthSettings):
        self.settings = settings
        self.headers = _get_headers(settings.access_token)
