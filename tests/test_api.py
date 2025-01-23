from dataclasses import dataclass
from typing import Any, Callable, Generator, NamedTuple
from unittest.mock import MagicMock

import pytest

from fediboat.api.timelines import (
    notification_timeline_generator,
    status_timeline_generator,
    thread_fetcher,
)
from fediboat.entities import Status, TUIEntity
from fediboat.settings import AuthSettings


class ResponseData(NamedTuple):
    json: Any
    validated: list[TUIEntity]


@dataclass
class ExpectedResponse:
    new: ResponseData
    old: ResponseData


@dataclass
class ExpectedThreadResponse(ExpectedResponse):
    status: Status


@pytest.mark.parametrize(
    "timeline_generator,expected_entities_fixture",
    [
        (status_timeline_generator, "expected_statuses"),
        (notification_timeline_generator, "expected_notifications"),
    ],
)
def test_timeline_api(
    session: MagicMock,
    timeline_generator: Callable[..., Generator[list[TUIEntity]]],
    expected_entities_fixture: str,
    settings: AuthSettings,
    monkeypatch: pytest.MonkeyPatch,
    request: pytest.FixtureRequest,
):
    expected_response: ExpectedResponse = request.getfixturevalue(
        expected_entities_fixture
    )
    response_mock = session.get.return_value
    response_mock.json.return_value = expected_response.new.json
    timeline = timeline_generator(
        session, f"{settings.instance_url}/api/endpoint", limit=20
    )

    response_entities = next(timeline)
    session.get.assert_called_with(f"{settings.instance_url}/api/endpoint?limit=20")
    assert len(response_entities) == 1
    assert len(expected_response.new.validated) == 1
    assert response_entities == expected_response.new.validated

    response_mock.json.return_value = expected_response.old.json
    response_mock.links = {
        "next": {
            "url": f"{settings.instance_url}/api/endpoint?max_id=7163058",
            "rel": "next",
        }
    }
    response_entities = next(timeline)
    assert len(expected_response.old.validated) == 1
    assert response_entities == expected_response.old.validated

    with pytest.raises(StopIteration):
        response_entities = next(timeline)


def test_thread_api(
    session: MagicMock, expected_thread: ExpectedThreadResponse, settings: AuthSettings
):
    response_mock = session.get.return_value
    response_mock.json.return_value = expected_thread.old.json

    fetch_thread = thread_fetcher(session, settings, expected_thread.status)
    statuses = fetch_thread()
    session.get.assert_called_with(
        f"{settings.instance_url}/api/v1/statuses/{expected_thread.status.id}/context"
    )
    assert statuses == expected_thread.old.validated

    response_mock.json.return_value = expected_thread.new.json
    statuses = fetch_thread()
    assert statuses == expected_thread.new.validated
