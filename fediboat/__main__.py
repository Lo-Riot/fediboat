from typing import Generic, Protocol, TypeVar
import click

from markdownify import markdownify as md
from pydantic import TypeAdapter
from rich.text import Text

from textual import events, on, log
from textual.app import App, ComposeResult
from textual.css.query import QueryType
from textual.screen import ModalScreen, Screen
from textual.widgets import (
    DataTable,
    Footer,
    Header,
    Input,
    Markdown,
)

from fediboat.api.timelines import (
    NotificationAPI,
    PersonalAPI,
    PublicRemoteTimelineAPI,
    BaseAPI,
    ThreadAPI,
    TimelineAPI,
    LocalTimelineAPI,
)
from fediboat.cli import cli
from fediboat.entities import Notification, Status
from fediboat.settings import load_settings

Base = TypeVar("Base", bound=BaseAPI, covariant=True)
BaseStatus = TypeVar("BaseStatus", bound=BaseAPI[Status], covariant=True)
Timeline = TypeVar("Timeline", bound=TimelineAPI, covariant=True)


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
        ("n", "switch('Notification')", "Notifications"),
        ("p", "switch('Personal')", "Personal"),
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


class StatusContent(Screen):
    BINDINGS = [("q", "app.pop_screen", "Go back")]

    def __init__(self, content: str | None = None):
        self.content = content
        super().__init__()

    def compose(self) -> ComposeResult:
        yield Markdown(self.content)
        yield Header()
        yield Footer()


class BaseTimeline(Screen, Generic[Base]):
    BINDINGS = [
        ("r", "update_timeline_new", "Refresh"),
        ("g", "switch_timeline", "Switch timeline"),
        ("j", "cursor_down"),
        ("k", "cursor_up"),
        ("l", "select_row"),
        ("ctrl+u", "scroll_up"),
        ("ctrl+d", "scroll_down"),
        ("q", "exit", "Quit"),
    ]

    CSS_PATH = "timeline.tcss"

    def __init__(self, mastodon_api: Base):
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

    def action_switch_timeline(self) -> None:
        def switch_timeline(timeline_name: str):
            timelines: dict[str, Screen] = {
                "Home": StatusTimeline(
                    TimelineAPI[Status](
                        self.mastodon_api.settings,
                        validator=TypeAdapter(list[Status]),
                    ),
                ),
                "Local": StatusTimeline(
                    LocalTimelineAPI(self.mastodon_api.settings),
                ),
                "Global": StatusTimeline(
                    PublicRemoteTimelineAPI(self.mastodon_api.settings),
                ),
                "Notification": NotificationTimeline(
                    NotificationAPI(self.mastodon_api.settings),
                ),
                "Personal": PersonalTimeline(
                    PersonalAPI(self.mastodon_api.settings),
                ),
            }
            timeline = timelines[timeline_name]
            timeline.sub_title = f"{timeline_name} Timeline"
            self.app.switch_screen(timeline)

        self.app.push_screen(SwitchTimeline(), switch_timeline)

    def action_update_timeline_new(self) -> None:
        self.mastodon_api.fetch_new()
        self._add_rows()

    def _add_rows(self) -> None:
        pass

    def on_key(self, event: events.Key):
        if event.character is None or not event.character.isdigit():
            return

        def jump_to_row(index: int):
            self.query_one(DataTable).move_cursor(row=index - 1)

        self.app.push_screen(Jump(event.character), jump_to_row)

    def action_exit(self) -> None:
        if len(self.app.screen_stack) > 2:
            self.app.pop_screen()  # If one or more threads are open
        else:
            self.app.exit()

    def action_scroll_down(self) -> None:
        timeline = self.query_one(DataTable)
        half_timeline_height = round(timeline.scrollable_content_region.height / 2)
        timeline.scroll_relative(y=half_timeline_height, animate=False)

    def action_scroll_up(self) -> None:
        timeline = self.query_one(DataTable)
        half_timeline_height = round(timeline.scrollable_content_region.height / 2)
        timeline.scroll_relative(y=-half_timeline_height, animate=False)

    def action_cursor_up(self) -> None:
        self.query_one(DataTable).action_cursor_up()

    def action_cursor_down(self) -> None:
        timeline = self.query_one(DataTable)
        timeline.action_cursor_down()

    def action_select_row(self) -> None:
        self.query_one(DataTable).action_select_cursor()


class TimelineNextPageProtocol(Protocol):
    @property
    def mastodon_api(self) -> TimelineAPI: ...

    def _add_rows(self) -> None: ...

    def query_one(self, selector: type[QueryType]) -> QueryType: ...

    def action_cursor_down(self) -> None: ...

    def action_update_timeline_old(self) -> None: ...


class TimelineNextPageMixin:
    def action_update_timeline_old(
        self: TimelineNextPageProtocol,
    ) -> None:
        self.mastodon_api.fetch_old()
        self._add_rows()

    def action_cursor_down(self: TimelineNextPageProtocol) -> None:
        timeline = self.query_one(DataTable)

        if timeline.cursor_row == timeline.row_count - 1:
            old_row_index = timeline.cursor_row
            self.action_update_timeline_old()
            timeline.move_cursor(row=old_row_index)

        timeline.action_cursor_down()


class BaseStatusTimeline(BaseTimeline[BaseStatus]):
    BINDINGS = [
        ("t", "open_thread", "Open thread"),
    ]

    def action_open_thread(self) -> None:
        timeline = self.query_one(DataTable)
        row_index = timeline.cursor_row
        selected_status = self.mastodon_api.get_entity(row_index)

        thread_api = ThreadAPI(self.mastodon_api.settings, selected_status)
        self.app.push_screen(ThreadTimeline(thread_api))

    def on_data_table_row_selected(self, row_selected: DataTable.RowSelected) -> None:
        row_index = self.query_one(DataTable).get_row_index(row_selected.row_key)
        selected_status = self.mastodon_api.get_entity(row_index)
        markdown = md(selected_status.content)
        self.app.push_screen(StatusContent(markdown))

    def _add_rows(self) -> None:
        timeline = self.query_one(DataTable)
        timeline.clear()
        for row_index, status in enumerate(self.mastodon_api.entities):
            created_at = status.created_at.astimezone()
            timeline.add_row(
                Text(str(row_index + 1), "#708090"),
                Text(created_at.strftime("%b %d %H:%M"), "#B0C4DE"),
                Text(status.account.acct, "#DDA0DD"),
                Text(md(status.content), "#F5DEB3"),
                Text("↵", "#87CEFA") if status.in_reply_to_id is not None else "",
            )


class NotificationTimeline(
    TimelineNextPageMixin,
    BaseTimeline[TimelineAPI[Notification]],
):
    def _add_rows(self) -> None:
        timeline = self.query_one(DataTable)
        timeline.clear()
        for row_index, notification in enumerate(self.mastodon_api.entities):
            created_at = notification.created_at.astimezone()
            timeline.add_row(
                Text(str(row_index + 1), "#708090"),
                Text(created_at.strftime("%b %d %H:%M"), "#B0C4DE"),
                Text(notification.account.acct, "#DDA0DD"),
                Text(
                    md(notification.status.content)
                    if notification.status is not None
                    else "",
                    "#F5DEB3",
                ),
            )


class StatusTimeline(
    TimelineNextPageMixin,
    BaseStatusTimeline[TimelineAPI[Status]],
):
    pass


class ThreadTimeline(BaseStatusTimeline[ThreadAPI]):
    pass


class PersonalTimeline(
    TimelineNextPageMixin,
    BaseStatusTimeline[PersonalAPI],
):
    pass


class FediboatApp(App):
    """Fediboat - Mastodon TUI client"""

    def __init__(self, mastodon_api: TimelineAPI[Status]):
        self.mastodon_api = mastodon_api
        super().__init__()

    def on_mount(self) -> None:
        self.title = "Fediboat"
        self.sub_title = "Home Timeline"
        self.install_screen(StatusContent(), name="status")
        self.push_screen(StatusTimeline(self.mastodon_api))


@cli.command()
@click.pass_context
def tui(ctx):
    settings = load_settings(ctx.obj["AUTH_SETTINGS"].expanduser())
    timeline_api = TimelineAPI[Status](
        settings.auth, validator=TypeAdapter(list[Status])
    )
    app = FediboatApp(timeline_api)
    app.run()


if __name__ == "__main__":
    cli()
