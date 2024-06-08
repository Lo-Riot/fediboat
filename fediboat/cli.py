import sys
import click
import webbrowser

from pathlib import Path

from .api.account import (
    create_app,
    auth,
    verify_credentials,
    APIError,
)
from fediboat.settings import (
    create_auth_settings,
    load_settings,
    AuthSettings,
    LoadSettingsError,
)


@click.group()
@click.option("-a", "--auth", default="~/.config/fediboat/auth.json", type=Path)
@click.pass_context
def cli(ctx, auth: Path):
    ctx.ensure_object(dict)
    ctx.obj["AUTH_SETTINGS"] = auth


def _login_account() -> AuthSettings:
    instance_url = click.prompt(
        "Instance url",
        default="https://mastodon.social",
    )
    app = create_app(instance_url)
    webbrowser.open(
        f"{instance_url}/oauth/authorize"
        f"?client_id={app['client_id']}&scope=read+write+follow"
        f"&redirect_uri=urn:ietf:wg:oauth:2.0:oob&response_type=code"
    )

    authz_code = click.prompt("Code")
    access_token = auth(
        instance_url, app["client_id"], app["client_secret"], authz_code
    )
    user = verify_credentials(instance_url, access_token)

    instance_domain = instance_url.replace("https://", "")
    full_username = f"{user['acct']}@{instance_domain}"

    auth_settings = AuthSettings(
        instance_url,
        instance_domain,
        full_username,
        access_token,
        app["client_id"],
        app["client_secret"],
    )
    return auth_settings


@cli.command()
@click.pass_context
def login(ctx):
    auth_settings_file = ctx.obj["AUTH_SETTINGS"].expanduser()

    try:
        auth_settings = load_settings(auth_settings_file).auth
        verify_credentials(
            auth_settings.instance_url,
            auth_settings.access_token,
        )
    except LoadSettingsError:
        auth_settings = _login_account()
        create_auth_settings(
            auth_settings_file,
            auth_settings,
        )
    except APIError as e:
        click.secho(f"Error: {e}", err=True, fg="red")
        sys.exit(1)

    click.secho("Logged in successfully!", fg="green")
