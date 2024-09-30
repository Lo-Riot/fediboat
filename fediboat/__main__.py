import click

from markdownify import markdownify as md
from rich.text import Text

from textual import events, on, log
from textual.app import App, ComposeResult
from textual.screen import ModalScreen, Screen
from textual.widgets import (
    DataTable,
    Footer,
    Header,
    Input,
    Markdown,
)

from fediboat.api.timelines import (
    PublicRemoteTimelineAPI,
    BaseAPI,
    ThreadAPI,
    TimelineAPI,
    LocalTimelineAPI,
)
from fediboat.cli import cli
from fediboat.settings import load_settings


class Jump(ModalScreen[int]):
    BINDINGS = [("escape", "app.pop_screen")]

    def __init__(self, character: str):
        self.character = character
        super().__init__()

    def compose(self) -> ComposeResult:
        yield Input(self.character, type="integer")

    @on(Input.Submitted)
    def submit(self) -> None:
        self.dismiss(int(self.query_one(Input).value))


class SwitchTimeline(ModalScreen[str]):
    BINDINGS = [
        ("h", "switch('Home')", "Home"),
        ("l", "switch('Local')", "Local"),
        ("n", "switch('')", "Notifications"),
        ("p", "switch('')", "Personal"),
        ("b", "switch('')", "Bookmarks"),
        ("c", "switch('')", "Conversations"),
        ("s", "switch('')", "Lists"),
        ("g", "switch('Global')", "Global"),
    ]

    def compose(self) -> ComposeResult:
        yield Footer()

    def on_key(self, event: events.Key):
        if self.active_bindings.get(event.key) is None:
            self.dismiss()

    def action_switch(self, timeline_name: str):
        self.dismiss(timeline_name)


class Status(Screen):
    BINDINGS = [("q", "app.pop_screen", "Go back")]

    def __init__(self, content: str | None = None):
        self.content = content
        super().__init__()

    def compose(self) -> ComposeResult:
        yield Markdown(self.content)
        yield Header()
        yield Footer()


class Timeline(Screen):
    BINDINGS = [
        ("j", "cursor_down"),
        ("k", "cursor_up"),
        ("l", "select_status"),
        ("q", "exit", "Quit"),
        ("r", "update_timeline_new", "Refresh"),
        ("g", "switch_timeline", "Switch timeline"),
        ("t", "open_thread", "Open thread"),
    ]

    CSS_PATH = "timeline.tcss"

    def __init__(self, mastodon_api: BaseAPI):
        self.mastodon_api = mastodon_api
        super().__init__()

    def on_mount(self) -> None:
        timeline = self.query_one(DataTable)

        timeline.cursor_background_priority = "renderable"

        timeline.add_columns("id", "date")
        timeline.add_column("user", width=25)
        timeline.add_column("title", width=50)
        timeline.add_column("is_reply", width=1)

        self.action_update_timeline_new()

    def compose(self) -> ComposeResult:
        yield DataTable(id="timeline", cursor_type="row", show_header=False)
        yield Header()
        yield Footer()

    def on_data_table_row_selected(self, row_selected: DataTable.RowSelected) -> None:
        row_index = self.query_one(DataTable).get_row_index(row_selected.row_key)
        selected_status = self.mastodon_api.get_entity(row_index)
        markdown = md(selected_status.content)
        self.app.push_screen(Status(markdown))

    def on_key(self, event: events.Key):
        if event.character is None or not event.character.isdigit():
            return

        def jump_to_status(index: int):
            self.query_one(DataTable).move_cursor(row=index - 1)

        self.app.push_screen(Jump(event.character), jump_to_status)

    def action_switch_timeline(self) -> None:
        def switch_timeline(timeline_name: str):
            if not isinstance(self.mastodon_api, TimelineAPI):
                return

            timelines: dict[str, type[TimelineAPI]] = {
                "Home": TimelineAPI,
                "Local": LocalTimelineAPI,
                "Global": PublicRemoteTimelineAPI,
            }
            timeline = timelines[timeline_name]
            self.mastodon_api = timeline(settings=self.mastodon_api.settings)
            self.sub_title = f"{timeline_name} Timeline"
            self.action_update_timeline_new()

        self.app.push_screen(SwitchTimeline(), switch_timeline)

    def action_update_timeline_new(self) -> None:
        statuses = self.mastodon_api.fetch_new()
        self._add_rows(statuses)

    def action_update_timeline_old(self) -> None:
        statuses = self.mastodon_api.fetch_old()
        self._add_rows(statuses)

    def _add_rows(self, entities: list) -> None:
        timeline = self.query_one(DataTable)
        timeline.clear()
        for row_index, status in enumerate(entities):
            created_at = status.created_at.astimezone()
            timeline.add_row(
                Text(str(row_index + 1), "#708090"),
                Text(created_at.strftime("%b %d %H:%M"), "#B0C4DE"),
                Text(status.account.acct, "#DDA0DD"),
                Text(md(status.content), "#F5DEB3"),
                Text("↵", "#87CEFA") if status.in_reply_to_id is not None else "",
            )

    def action_open_thread(self) -> None:
        timeline = self.query_one(DataTable)
        row_index = timeline.cursor_row

        selected_status = self.mastodon_api.get_entity(row_index)
        thread_api = ThreadAPI(self.mastodon_api.settings, selected_status)
        self.app.push_screen(Timeline(thread_api))

    def action_exit(self) -> None:
        if len(self.app.screen_stack) > 2:
            self.app.pop_screen()  # If one or more threads are open
        else:
            self.app.exit()

    def action_cursor_up(self) -> None:
        self.query_one(DataTable).action_cursor_up()

    def action_cursor_down(self) -> None:
        timeline = self.query_one(DataTable)
        timeline.action_cursor_down()
        if timeline.cursor_row == timeline.row_count - 1:
            self.action_update_timeline_old()

    def action_select_status(self) -> None:
        self.query_one(DataTable).action_select_cursor()


class FediboatApp(App):
    """Fediboat - Mastodon TUI client"""

    def __init__(self, mastodon_api: BaseAPI):
        self.mastodon_api = mastodon_api
        super().__init__()

    def on_mount(self) -> None:
        self.title = "Fediboat"
        self.sub_title = "Home timeline"
        self.install_screen(Status(), name="status")
        self.push_screen(Timeline(self.mastodon_api))


@cli.command()
@click.pass_context
def tui(ctx):
    settings = load_settings(ctx.obj["AUTH_SETTINGS"].expanduser())
    timeline_api = TimelineAPI(settings.auth)
    app = FediboatApp(timeline_api)
    app.run()


if __name__ == "__main__":
    cli()
