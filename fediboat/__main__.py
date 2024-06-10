import click

from markdownify import markdownify as md
from rich.text import Text

from textual.app import App, ComposeResult
from textual.reactive import reactive
from textual.screen import Screen
from textual.widgets import DataTable, Footer, Header, Markdown

from fediboat.api.timeline import TimelineAPI
from fediboat.cli import cli
from fediboat.settings import load_settings


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

        timeline.cursor_background_priority = "renderable"

        timeline.add_columns("id", "date")
        timeline.add_column("user", width=25)
        timeline.add_column("title", width=50)
        timeline.add_column("is_reply", width=1)

        self.action_update_timeline()

    def on_data_table_row_selected(self, row_selected: DataTable.RowSelected) -> None:
        selected_content = self.query_one(DataTable).get_row(row_selected.row_key)
        status_screen = self.app.get_screen("status")
        status_screen.content = selected_content[3]
        self.app.push_screen(status_screen)

    def action_update_timeline(self) -> None:
        statuses = self.timeline_api.update()

        timeline = self.query_one(DataTable)
        timeline.clear()
        for row_index, status in enumerate(statuses):
            timeline.add_row(
                Text(str(row_index + 1), "#708090"),
                Text(status.created_at.strftime("%b %d %H:%M"), "#B0C4DE"),
                Text(status.account.acct, "#DDA0DD"),
                Text(md(status.content), "#F5DEB3"),
                Text("↵", "#87CEFA") if status.in_reply_to_id is not None else "",
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
