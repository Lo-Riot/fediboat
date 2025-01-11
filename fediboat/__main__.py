from typing import Callable, Generator
import tempfile
import subprocess

import click
from markdownify import markdownify as md
from requests import Session
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

from fediboat.api.auth import get_headers
from fediboat.api.timelines import (
    TUIEntity,
    bookmarks_timeline_generator,
    thread_fetcher,
    global_timeline_generator,
    home_timeline_generator,
    local_timeline_generator,
    notifications_timeline_generator,
    personal_timeline_generator,
    post_status,
)
from fediboat.cli import cli
from fediboat.settings import AuthSettings, Settings, load_settings


class Jump(ModalScreen[int]):
    BINDINGS = [("escape", "app.pop_screen")]

    def __init__(self, character: str):
        self.character = character
        super().__init__()

    def compose(self) -> ComposeResult:
        yield Input(self.character, select_on_focus=False, type="integer")

    @on(Input.Submitted)
    def submit(self) -> None:
        self.dismiss(int(self.query_one(Input).value))


class SwitchTimeline(ModalScreen[str]):
    BINDINGS = [
        ("h", "switch('Home')", "Home"),
        ("l", "switch('Local')", "Local"),
        ("n", "switch('Notifications')", "Notifications"),
        ("p", "switch('Personal')", "Personal"),
        ("b", "switch('Bookmarks')", "Bookmarks"),
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


class BaseTimeline(Screen):
    BINDINGS = [
        ("r", "update_timeline_new", "Refresh"),
        ("g", "switch_timeline", "Switch timeline"),
        ("t", "open_thread", "Open thread"),
        ("p", "post_status", "Post"),
        ("j", "cursor_down"),
        ("k", "cursor_up"),
        ("l", "select_row"),
        ("ctrl+u", "scroll_up"),
        ("ctrl+d", "scroll_down"),
        ("q", "exit", "Quit"),
    ]

    CSS_PATH = "timeline.tcss"

    def __init__(
        self,
        timelines: dict[
            str, Callable[[Session, AuthSettings], Generator[list[TUIEntity]]]
        ],
        settings: Settings,
        session: Session,
        current_timeline_name: str = "Home",
    ):
        self.timelines = timelines
        self.current_timeline_name = current_timeline_name
        self.settings = settings
        self.session = session
        self.current_timeline = timelines[current_timeline_name](session, settings.auth)
        self.entities: list[TUIEntity] = []
        self.notification_signs: dict[str, tuple[str, str]] = {
            "favourite": ("★", "#FFD32C"),
            "mention": ("@", "#82C8E5"),
            "reblog": ("⮂", "#79BD9A"),
            "follow": ("+", ""),
            "follow_request": ("r", ""),
            "moderation_warning": ("w", "#C04657"),
        }
        super().__init__()

    def on_mount(self) -> None:
        timeline = self.query_one(DataTable)

        timeline.cursor_background_priority = "renderable"
        timeline.add_columns("id", "date")
        timeline.add_column("user", width=25)
        timeline.add_column("title", width=50)
        timeline.add_column("is_reply", width=1)
        timeline.add_column("notification_type", width=1)
        self.action_update_timeline_new()

    def compose(self) -> ComposeResult:
        yield DataTable(id="timeline", cursor_type="row", show_header=False)
        yield Header()
        yield Footer()

    def action_switch_timeline(self) -> None:
        def switch_timeline(timeline_name: str | None):
            if timeline_name is None:
                return

            if len(self.app.screen_stack) > 2:
                for _ in self.app.screen_stack[2:]:
                    self.app.pop_screen()

            self.app.switch_screen(
                Timeline(self.timelines, self.settings, self.session, timeline_name)
            )

        self.app.push_screen(SwitchTimeline(), switch_timeline)

    def action_update_timeline_new(self) -> None:
        pass

    def action_post_status(self) -> None:
        with self.app.suspend():
            with tempfile.NamedTemporaryFile() as tmp:
                subprocess.run([self.settings.config.editor, tmp.name])
                content = tmp.read().decode("utf-8")

            if not content:
                return

        post_status(content, self.session, self.settings.auth)

    def _add_rows(self) -> None:
        timeline = self.query_one(DataTable)
        timeline.clear()
        for row_index, entity in enumerate(self.entities):
            created_at = entity.created_at.astimezone()
            timeline.add_row(
                Text(str(row_index + 1), "#708090"),
                Text(created_at.strftime("%b %d %H:%M"), "#B0C4DE"),
                Text(entity.author, "#DDA0DD"),
                Text(md(entity.content), "#F5DEB3")
                if entity.content is not None
                else "",
                Text("↵", "#87CEFA") if entity.in_reply_to_id is not None else "",
                Text(*self.notification_signs.get(entity.notification_type) or "")
                if entity.notification_type is not None
                else "",
            )

    def action_open_thread(self) -> None:
        timeline = self.query_one(DataTable)
        row_index = timeline.cursor_row
        selected_status = self.entities[row_index]

        fetch_thread = thread_fetcher(self.session, self.settings.auth, selected_status)
        self.app.push_screen(
            ThreadTimeline(
                self.timelines,
                self.settings,
                self.session,
                fetch_thread,
                self.current_timeline_name,
            )
        )

    def on_data_table_row_selected(self, row_selected: DataTable.RowSelected) -> None:
        row_index = self.query_one(DataTable).get_row_index(row_selected.row_key)
        selected_status = self.entities[row_index]
        markdown = md(selected_status.content)
        self.app.push_screen(StatusContent(markdown))

    def on_key(self, event: events.Key):
        if event.character is None or not event.character.isdigit():
            return

        def jump_to_row(index: int | None):
            if index is not None:
                index -= 1
            self.query_one(DataTable).move_cursor(row=index)

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


class Timeline(BaseTimeline):
    def __init__(
        self,
        timelines: dict[
            str, Callable[[Session, AuthSettings], Generator[list[TUIEntity]]]
        ],
        settings: Settings,
        session: Session,
        current_timeline_name: str = "Home",
    ):
        super().__init__(timelines, settings, session, current_timeline_name)
        self.screen.sub_title = f"{current_timeline_name} Timeline"

    def action_update_timeline_old(self) -> None:
        try:
            new_entities = next(self.current_timeline)
        except StopIteration:
            return

        self.entities.extend(new_entities)
        self._add_rows()

    def action_cursor_down(self) -> None:
        timeline = self.query_one(DataTable)

        if timeline.cursor_row == timeline.row_count - 1:
            old_row_index = timeline.cursor_row
            self.action_update_timeline_old()
            timeline.move_cursor(row=old_row_index)

        timeline.action_cursor_down()

    def action_update_timeline_new(self) -> None:
        self.current_timeline = self.timelines[self.current_timeline_name](
            self.session, self.settings.auth
        )
        self.entities = next(self.current_timeline)
        self._add_rows()


class ThreadTimeline(BaseTimeline):
    def __init__(
        self,
        timelines: dict[
            str, Callable[[Session, AuthSettings], Generator[list[TUIEntity]]]
        ],
        settings: Settings,
        session: Session,
        fetch_thread: Callable[..., list[TUIEntity]],
        current_timeline_name: str = "Home",
    ):
        super().__init__(timelines, settings, session, current_timeline_name)
        self.fetch_thread = fetch_thread
        self.screen.sub_title = "Thread Timeline"

    def action_update_timeline_new(self) -> None:
        self.entities = self.fetch_thread()
        self._add_rows()


class FediboatApp(App):
    """Fediboat - Mastodon TUI client"""

    def __init__(
        self,
        timelines: dict[
            str, Callable[[Session, AuthSettings], Generator[list[TUIEntity]]]
        ],
        settings: Settings,
        session: Session,
    ):
        self.timelines = timelines
        self.settings = settings
        self.session = session
        super().__init__()

    def on_mount(self) -> None:
        self.title = "Fediboat"
        self.install_screen(StatusContent(), name="status")
        self.push_screen(Timeline(self.timelines, self.settings, self.session))


@cli.command()
@click.pass_context
def tui(ctx):
    auth_settings_file = ctx.obj["AUTH_SETTINGS"].expanduser()
    config_file = ctx.obj["CONFIG"].expanduser()
    settings = load_settings(auth_settings_file, config_file)

    session = Session()
    session.headers.update(get_headers(settings.auth.access_token))
    timelines: dict[
        str, Callable[[Session, AuthSettings], Generator[list[TUIEntity]]]
    ] = {
        "Home": home_timeline_generator,
        "Local": local_timeline_generator,
        "Global": global_timeline_generator,
        "Notifications": notifications_timeline_generator,
        "Personal": personal_timeline_generator,
        "Bookmarks": bookmarks_timeline_generator,
    }

    app = FediboatApp(timelines, settings, session)
    app.run()


if __name__ == "__main__":
    cli()
