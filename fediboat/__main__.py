from pathlib import Path
import click
from textual.app import App, ComposeResult
from textual.reactive import reactive
from textual.screen import Screen
from textual.widgets import DataTable, Footer, Header, Markdown
from fediboat.api.timeline import TimelineAPI

from fediboat.cli import cli
from fediboat.settings import Settings, load_settings


class Status(Screen):
    BINDINGS = [("q", "app.pop_screen", "Go back")]
    content = reactive("", recompose=True)

    def compose(self) -> ComposeResult:
        yield Markdown(self.content)
        yield Header()
        yield Footer()


class FediboatApp(App):
    """Fediboat - Mastodon TUI client"""

    BINDINGS = [
        ("q", "quit", "Quit"),
        ("j", "cursor_down"),
        ("k", "cursor_up"),
        ("l", "select_status"),
        ("r", "update_timeline", "Refresh"),
    ]

    CSS_PATH = "timeline.tcss"

    def __init__(self, timeline_api: TimelineAPI):
        self.timeline_api = timeline_api
        super().__init__()

    def compose(self) -> ComposeResult:
        yield DataTable(id="timeline", cursor_type="row", show_header=False)
        yield Header()
        yield Footer()

    def on_mount(self) -> None:
        self.title = "Fediboat"
        self.sub_title = "Home timeline"
        self.install_screen(Status(), name="status")

        timeline = self.query_one(DataTable)

        timeline.add_columns("id", "date")
        timeline.add_column("user", width=25)
        timeline.add_column("title", width=50)

        self.action_update_timeline()

    def on_data_table_row_selected(self, row_selected: DataTable.RowSelected) -> None:
        selected_content = self.query_one(DataTable).get_row(row_selected.row_key)
        status_screen = self.app.get_screen("status")
        status_screen.content = selected_content[3]
        self.app.push_screen(status_screen)

    def action_update_timeline(self) -> None:
        timeline_data = self.timeline_api.update()

        timeline = self.query_one(DataTable)
        timeline.clear()
        for status_id, status in enumerate(timeline_data):
            timeline.add_row(
                status_id + 1,
                status["created_at"],
                status["account"]["acct"],
                status["content"],
            )

    def action_cursor_up(self) -> None:
        self.query_one(DataTable).action_cursor_up()

    def action_cursor_down(self) -> None:
        self.query_one(DataTable).action_cursor_down()

    def action_select_status(self) -> None:
        self.query_one(DataTable).action_select_cursor()


@cli.command()
@click.pass_context
def tui(ctx):
    settings = load_settings(ctx.obj["AUTH_SETTINGS"].expanduser())
    timeline_api = TimelineAPI(settings.auth)
    app = FediboatApp(timeline_api)
    app.run()


if __name__ == "__main__":
    cli()
