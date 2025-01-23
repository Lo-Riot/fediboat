from typing import Callable

from requests import Session
from textual import events
from textual.app import ComposeResult
from textual.screen import ModalScreen
from textual.widgets import (
    DataTable,
    Footer,
)

from fediboat.api.auth import APIError
from fediboat.api.timelines import TimelineCallable, thread_fetcher
from fediboat.entities import TUIEntity
from fediboat.screens.base import BaseTimeline
from fediboat.settings import (
    Settings,
)


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


class Timeline(BaseTimeline):
    def action_switch_timeline(self) -> None:
        def switch_timeline(timeline_name: str | None):
            if timeline_name is None:
                return

            if len(self.app.screen_stack) > 2:
                for _ in self.app.screen_stack[2:]:
                    self.app.pop_screen()

            self.app.switch_screen(
                EntityTimeline(
                    self.timelines, self.settings, self.session, timeline_name
                )
            )

        self.app.push_screen(SwitchTimeline(), switch_timeline)

    def action_open_thread(self) -> None:
        if len(self.entities) == 0:
            return

        timeline = self.query_one(DataTable)
        row_index = timeline.cursor_row
        selected_entity = self.entities[row_index]
        if selected_entity.status is None:
            return

        fetch_thread = thread_fetcher(
            self.session, self.settings.auth, selected_entity.status
        )
        self.app.push_screen(
            ThreadTimeline(
                self.timelines,
                self.settings,
                self.session,
                fetch_thread,
                self.current_timeline_name,
            )
        )


class EntityTimeline(Timeline):
    def __init__(
        self,
        timelines: dict[str, TimelineCallable],
        settings: Settings,
        session: Session,
        current_timeline_name: str = "Home",
        refresh_at_start: bool = True,
    ):
        super().__init__(
            timelines,
            settings,
            session,
            current_timeline_name,
            refresh_at_start,
        )
        self.screen.sub_title = f"{current_timeline_name} Timeline"

    def action_update_timeline_old(self) -> None:
        try:
            new_entities = next(self.current_timeline)
        except APIError as e:
            self.log_error_message(str(e))
            return
        except StopIteration:
            return

        self.entities.extend(new_entities)
        self.add_rows()

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
        try:
            self.entities = next(self.current_timeline)
        except APIError as e:
            self.log_error_message(str(e))
            return
        self.add_rows()


class ThreadTimeline(Timeline):
    def __init__(
        self,
        timelines: dict[str, TimelineCallable],
        settings: Settings,
        session: Session,
        fetch_thread: Callable[..., list[TUIEntity]],
        current_timeline_name: str,
    ):
        super().__init__(timelines, settings, session, current_timeline_name)
        self.fetch_thread = fetch_thread
        self.screen.sub_title = "Thread Timeline"

    def action_update_timeline_new(self) -> None:
        try:
            self.entities = self.fetch_thread()
        except APIError as e:
            self.log_error_message(str(e))
            return
        self.add_rows()
