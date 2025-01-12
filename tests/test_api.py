import json
from dataclasses import dataclass
from typing import Any, Callable, Generator, NamedTuple
from unittest.mock import MagicMock

import pytest
from pydantic import TypeAdapter
from requests import Session

from fediboat.api.timelines import (
    TUIEntity,
    context_to_tui_entities,
    notification_timeline_generator,
    notifications_to_tui_entities,
    status_timeline_generator,
    status_to_tui_entity,
    statuses_to_tui_entities,
    thread_fetcher,
)
from fediboat.entities import Context, Notification, Status
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
    status: TUIEntity


@pytest.fixture
def statuses_validator() -> TypeAdapter[list[Status]]:
    return TypeAdapter(list[Status])


@pytest.fixture
def notifications_validator() -> TypeAdapter[list[Notification]]:
    return TypeAdapter(list[Notification])


@pytest.fixture
def expected_statuses(
    statuses_validator: TypeAdapter[list[Status]],
) -> ExpectedResponse:
    with open("tests/data/statuses.json") as f:
        new_json = json.load(f)
    new_statuses = statuses_validator.validate_python(new_json)
    new_tui_entities = statuses_to_tui_entities(new_statuses)

    with open("tests/data/old_statuses.json") as f:
        old_json = json.load(f)
    old_statuses = statuses_validator.validate_python(old_json)
    old_tui_entities = statuses_to_tui_entities(old_statuses)

    return ExpectedResponse(
        ResponseData(new_json, new_tui_entities),
        ResponseData(old_json, old_tui_entities),
    )


@pytest.fixture
def expected_notifications(
    notifications_validator: TypeAdapter[list[Notification]],
) -> ExpectedResponse:
    with open("tests/data/notifications.json") as f:
        new_json = json.load(f)
    new_notifications = notifications_validator.validate_python(new_json)
    new_tui_entities = notifications_to_tui_entities(new_notifications)

    with open("tests/data/old_notifications.json") as f:
        old_json = json.load(f)
    old_notifications = notifications_validator.validate_python(old_json)
    old_tui_entities = notifications_to_tui_entities(old_notifications)

    return ExpectedResponse(
        ResponseData(new_json, new_tui_entities),
        ResponseData(old_json, old_tui_entities),
    )


@pytest.fixture
def expected_thread() -> ExpectedThreadResponse:
    with open("tests/data/thread_status.json") as f:
        thread_status = Status.model_validate_json(f.read())
    thread_tui_entity = status_to_tui_entity(thread_status)

    with open("tests/data/new_thread_statuses.json") as f:
        new_json = json.load(f)
    new_context = Context.model_validate(new_json)
    new_tui_entities = context_to_tui_entities(new_context, thread_tui_entity)

    with open("tests/data/old_thread_statuses.json") as f:
        old_json = json.load(f)
    old_context = Context.model_validate(old_json)
    old_tui_entities = context_to_tui_entities(old_context, thread_tui_entity)

    return ExpectedThreadResponse(
        ResponseData(
            new_json,
            new_tui_entities,
        ),
        ResponseData(
            old_json,
            old_tui_entities,
        ),
        thread_tui_entity,
    )


@pytest.fixture
def settings() -> AuthSettings:
    return AuthSettings(
        id="123456",
        instance_url="http://localhost",
        instance_domain="localhost",
        full_username="test_user@localhost",
        access_token="123",
        client_id="1234",
        client_secret="12345",
    )


@pytest.mark.parametrize(
    "timeline_generator,expected_entities_fixture",
    [
        (status_timeline_generator, "expected_statuses"),
        (notification_timeline_generator, "expected_notifications"),
    ],
)
def test_timeline_api(
    timeline_generator: Callable[..., Generator[list[TUIEntity]]],
    expected_entities_fixture: str,
    settings: AuthSettings,
    monkeypatch: pytest.MonkeyPatch,
    request: pytest.FixtureRequest,
):
    expected_response: ExpectedResponse = request.getfixturevalue(
        expected_entities_fixture
    )
    response_mock = MagicMock(**{"json.return_value": expected_response.new.json})
    get_request_mock = MagicMock(return_value=response_mock)
    session_mock = MagicMock(spec_set=Session, get=get_request_mock)
    timeline = timeline_generator(
        session_mock, f"{settings.instance_url}/api/endpoint", limit=20
    )

    response_entities = next(timeline)
    get_request_mock.assert_called_with(
        f"{settings.instance_url}/api/endpoint", params={"limit": 20}
    )
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


def test_thread_api(expected_thread: ExpectedThreadResponse, settings: AuthSettings):
    response_mock = MagicMock(**{"json.return_value": expected_thread.old.json})
    get_request_mock = MagicMock(return_value=response_mock)
    session_mock = MagicMock(spec_set=Session, get=get_request_mock)

    fetch_thread = thread_fetcher(session_mock, settings, expected_thread.status)
    statuses = fetch_thread()
    get_request_mock.assert_called_with(
        f"{settings.instance_url}/api/v1/statuses/{expected_thread.status.id}/context"
    )
    assert statuses == expected_thread.old.validated

    response_mock.json.return_value = expected_thread.new.json
    statuses = fetch_thread()
    assert statuses == expected_thread.new.validated
