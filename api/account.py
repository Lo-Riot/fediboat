import requests
import webbrowser


class APIError:
    pass


class LoginError(APIError):
    pass


class AppCreateError(APIError):
    pass


def create_app(instance_url: str) -> dict:
    return requests.post(
        f"{instance_url}/api/v1/apps",
        data={
            "client_name": "Feta",
            "redirect_uris": "urn:ietf:wg:oauth:2.0:oob",
            "scopes": "read write follow",
            "website": "https://github.com/Lo-Riot/feta",
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
            "scope": "read write push",
        },
    ).json()
    return resp["access_token"]


def verify_credentials(instance_url: str, access_token: str) -> dict:
    """Returns account id or raises LoginError"""
    return requests.get(
        f"{instance_url}/api/v1/accounts/verify_credentials",
        headers={"Authorization": f"Bearer {access_token}"},
    ).json()
