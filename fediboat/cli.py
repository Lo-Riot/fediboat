import sys
import webbrowser
from pathlib import Path

import click
from requests import Session
from textual.app import App

from fediboat.api.timelines import get_timelines, handle_request_errors
from fediboat.screens import StatusContent, TimelineScreen
from fediboat.settings import (
    AuthSettings,
    LoadSettingsError,
    create_auth_settings,
    load_settings,
)

from .api.auth import (
    APIError,
    auth,
    create_app,
    get_headers,
    verify_credentials,
)


class FediboatApp(App):
    """Fediboat - Mastodon TUI client"""

    def __init__(self, timeline: TimelineScreen):
        self.timeline = timeline
        super().__init__()

    def on_mount(self) -> None:
        self.title = "Fediboat"
        self.install_screen(StatusContent(), name="status")
        self.push_screen(self.timeline)


@click.group(help="Fediboat - Mastodon TUI client with a Newsboat-like interface")
@click.option(
    "-a",
    "--auth",
    default="~/.config/fediboat/auth.json",
    type=Path,
    show_default=True,
)
@click.option(
    "-c",
    "--config",
    default="~/.config/fediboat/config.toml",
    type=Path,
    show_default=True,
)
@click.pass_context
def cli(ctx, auth: Path, config: Path):
    ctx.ensure_object(dict)
    ctx.obj["AUTH_SETTINGS"] = auth
    ctx.obj["CONFIG"] = config


@cli.command()
@click.pass_context
def tui(ctx):
    auth_settings_file = ctx.obj["AUTH_SETTINGS"].expanduser()
    config_file = ctx.obj["CONFIG"].expanduser()
    try:
        settings = load_settings(auth_settings_file, config_file)
    except LoadSettingsError:
        click.secho("Error: Run the 'fediboat login' command first", err=True, fg="red")
        sys.exit(1)

    session = Session()
    session.headers.update(get_headers(settings.auth.access_token))
    session.hooks["response"].append(handle_request_errors)

    timeline = TimelineScreen(get_timelines(settings.config), settings, session)
    app = FediboatApp(timeline)
    app.run()


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
        id=user["id"],
        instance_url=instance_url,
        instance_domain=instance_domain,
        full_username=full_username,
        access_token=access_token,
        client_id=app["client_id"],
        client_secret=app["client_secret"],
    )
    return auth_settings


@cli.command()
@click.pass_context
def login(ctx):
    auth_settings_file = ctx.obj["AUTH_SETTINGS"].expanduser()
    config_file = ctx.obj["CONFIG"].expanduser()

    try:
        auth_settings = load_settings(auth_settings_file, config_file).auth
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
