import subprocess
import tempfile

from requests import Session
from rich.text import Text
from textual import events, log, on
from textual.app import ComposeResult
from textual.containers import Grid
from textual.screen import ModalScreen, Screen
from textual.widgets import (
    DataTable,
    Footer,
    Header,
    Input,
    Label,
    Markdown,
)

from fediboat.api.auth import APIError
from fediboat.api.timelines import (
    TimelineCallable,
    post_status,
)
from fediboat.entities import TUIEntity
from fediboat.settings import (
    Settings,
)


class ErrorMessage(ModalScreen):
    BINDINGS = [("escape", "app.pop_screen"), ("q", "app.pop_screen", "Quit")]

    def __init__(self, message: str):
        self.message = message
        super().__init__()

    def compose(self) -> ComposeResult:
        yield Grid(Label(self.message, id="message"), id="dialog")
        yield Footer()


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
        ("R", "reply", "Reply"),
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
        timelines: dict[str, TimelineCallable],
        settings: Settings,
        session: Session,
        current_timeline_name: str = "Home",
        refresh_at_start: bool = True,
    ):
        self.timelines = timelines
        self.current_timeline_name = current_timeline_name

        self.settings = settings
        self.config = settings.config
        self.session = session

        self.current_timeline = timelines[current_timeline_name](session, settings.auth)
        self.entities: list[TUIEntity] = []
        self.refresh_at_start = refresh_at_start
        super().__init__()

    def on_mount(self) -> None:
        timeline = self.query_one(DataTable)

        timeline.cursor_background_priority = "renderable"
        timeline.add_columns("id", "date")
        timeline.add_column("user", width=25)
        timeline.add_column("title", width=50)
        timeline.add_column("is_reply", width=1)
        timeline.add_column("notification_type", width=1)
        if self.refresh_at_start:
            self.action_update_timeline_new()

    def compose(self) -> ComposeResult:
        yield DataTable(id="timeline", cursor_type="row", show_header=False)
        yield Header()
        yield Footer()

    def action_update_timeline_new(self) -> None:
        pass

    def action_post_status(
        self,
        in_reply_to_id: str | None = None,
        mentions: str | None = None,
        visibility: str = "public",
    ) -> None:
        with self.app.suspend(), tempfile.NamedTemporaryFile() as tmp:
            if mentions is not None:
                tmp.write(mentions.encode("utf-8"))
                tmp.seek(0)
            subprocess.run([self.config.editor, tmp.name])
            content = tmp.read().decode("utf-8")

            if not content or content == mentions:
                return

        try:
            post_status(
                content,
                self.session,
                self.settings.auth,
                in_reply_to_id,
                visibility,
            )
        except APIError as e:
            self.log_error_message(str(e))
            return

    def action_reply(self):
        if len(self.entities) == 0:
            return

        timeline = self.query_one(DataTable)
        selected_entity = self.entities[timeline.cursor_row]
        if selected_entity.status is None:
            return

        mentions = ""
        for mention in selected_entity.status.mentions:
            mentions += f"@{mention.acct} "

        if selected_entity.status.account.acct not in mentions:
            mentions = f"@{selected_entity.status.account.acct} {mentions}"
        self.action_post_status(
            selected_entity.status.id, mentions, selected_entity.status.visibility
        )

    def add_rows(self) -> None:
        timeline = self.query_one(DataTable)
        timeline.clear()
        for row_index, entity in enumerate(self.entities):
            created_at = content = is_reply = ""
            if entity.status is not None:
                created_at = entity.status.created_at.astimezone().strftime(
                    "%b %d %H:%M"
                )
                content = " ".join(
                    line.strip() for line in entity.status.content[:50].splitlines()
                )
                is_reply = "↵" if entity.status.in_reply_to_id else ""

            sign: tuple[str, str] = ("", "")
            if entity.sign is not None:
                sign = self.config.notifications.signs.get(entity.sign, sign)

            timeline.add_row(
                Text(str(row_index + 1), "#708090"),
                Text(created_at, "#B0C4DE"),
                Text(entity.author, "#DDA0DD"),
                Text(content, "#F5DEB3"),
                Text(is_reply, "#87CEFA"),
                Text(*sign),
            )

    def log_error_message(self, message: str) -> None:
        log(f"Current timeline: {self.current_timeline_name}, Error:", message)
        self.app.push_screen(ErrorMessage(message))

    def on_data_table_row_selected(self, row_selected: DataTable.RowSelected) -> None:
        if len(self.entities) == 0:
            return

        selected_entity = self.entities[row_selected.cursor_row]
        if selected_entity.status is None:
            return

        markdown = selected_entity.status.content
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
