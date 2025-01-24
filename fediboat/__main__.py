import click
from requests import Session
from textual.app import App

from fediboat.api.auth import get_headers
from fediboat.api.timelines import get_timelines, handle_request_errors
from fediboat.cli import cli
from fediboat.screens import StatusContent, TimelineScreen
from fediboat.settings import load_settings


class FediboatApp(App):
    """Fediboat - Mastodon TUI client"""

    def __init__(self, timeline: TimelineScreen):
        self.timeline = timeline
        super().__init__()

    def on_mount(self) -> None:
        self.title = "Fediboat"
        self.install_screen(StatusContent(), name="status")
        self.push_screen(self.timeline)


@cli.command()
@click.pass_context
def tui(ctx):
    auth_settings_file = ctx.obj["AUTH_SETTINGS"].expanduser()
    config_file = ctx.obj["CONFIG"].expanduser()
    settings = load_settings(auth_settings_file, config_file)

    session = Session()
    session.headers.update(get_headers(settings.auth.access_token))
    session.hooks["response"].append(handle_request_errors)

    timeline = TimelineScreen(get_timelines(settings.config), settings, session)
    app = FediboatApp(timeline)
    app.run()


if __name__ == "__main__":
    cli()
