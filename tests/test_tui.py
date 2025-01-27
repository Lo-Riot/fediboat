from unittest.mock import MagicMock

import pytest
from rich.text import Text
from textual.widgets import DataTable

from fediboat.api.timelines import get_timelines
from fediboat.cli import FediboatApp
from fediboat.screens import StatusContent, SwitchTimeline, TimelineScreen
from fediboat.settings import AuthSettings, Config, Settings
from tests.test_api import ExpectedResponse, ExpectedThreadResponse

ID_COLUMN: int = 0
AUTHOR_COLUMN: int = 2

FIRST_ROW_INDEX: int = 0
LAST_ROW_INDEX: int = 1

FOOTER_MENU_KEY: str = "g"
BACK_OR_EXIT_KEY: str = "q"
DOWN_KEY: str = "j"
OPEN_THREAD_KEY: str = "t"


@pytest.fixture
def app(
    settings: AuthSettings, session: MagicMock, expected_statuses: ExpectedResponse
) -> FediboatApp:
    all_settings = Settings(settings, Config())
    timeline = TimelineScreen(
        get_timelines(all_settings.config),
        all_settings,
        session,
        refresh_at_start=False,
    )
    return FediboatApp(timeline)


@pytest.mark.parametrize(
    "select_timeline_key,expected_entities_fixture,timeline_name",
    [
        ("h", "expected_statuses", "Home"),
        ("n", "expected_notifications", "Notifications"),
    ],
)
async def test_timelines(
    app: FediboatApp,
    session: MagicMock,
    select_timeline_key: str,
    expected_entities_fixture: str,
    timeline_name: str,
    settings: AuthSettings,
    expected_thread: ExpectedThreadResponse,
    request: pytest.FixtureRequest,
):
    expected_response: ExpectedResponse = request.getfixturevalue(
        expected_entities_fixture
    )

    async with app.run_test() as pilot:
        assert isinstance(app.screen, TimelineScreen)

        await pilot.press(FOOTER_MENU_KEY)
        assert isinstance(app.screen, SwitchTimeline)

        response_mock = session.get.return_value
        response_mock.json.return_value = expected_response.new.json
        await pilot.press(select_timeline_key)

        timeline = app.screen.query_one(DataTable)
        assert timeline.row_count == 1

        row: list[Text] = timeline.get_row_at(FIRST_ROW_INDEX)
        assert row[ID_COLUMN] == Text("1")
        assert row[AUTHOR_COLUMN] == Text(expected_response.new.validated[0].author)

        await pilot.press("enter")
        assert len(app.screen_stack) == 3
        assert isinstance(app.screen, StatusContent)

        await pilot.press(BACK_OR_EXIT_KEY)
        assert len(app.screen_stack) == 2
        assert isinstance(app.screen, TimelineScreen)

        # Test updating old entities
        response_mock.json.return_value = expected_response.old.json
        await pilot.press(DOWN_KEY)
        assert timeline.row_count == 2

        assert app.screen.entities[LAST_ROW_INDEX] == expected_response.old.validated[0]
        row: list[Text] = timeline.get_row_at(LAST_ROW_INDEX)
        assert row[ID_COLUMN] == Text("2")

        await pilot.press(DOWN_KEY)
        assert timeline.row_count == 2
        with pytest.raises(StopIteration):
            next(app.screen.current_timeline)

        response_mock.json.return_value = expected_thread.old.json
        await pilot.press(OPEN_THREAD_KEY)
        assert len(app.screen_stack) == 3

        await pilot.press(BACK_OR_EXIT_KEY)
        assert len(app.screen_stack) == 2
