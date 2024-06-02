import requests


class APIError:
    pass


class LoginError(APIError):
    pass


class AppCreateError(APIError):
    pass


def create_application() -> str:
    """Returns app id or raises AppCreateError"""
    ...


def verify_credentials() -> str:
    """Returns account id or raises LoginError"""
    ...
