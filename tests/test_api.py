from dataclasses import dataclass
from typing import Generic, NamedTuple, Sequence, TypeAlias, TypeVar
from unittest.mock import MagicMock

import pytest
from pydantic import TypeAdapter

from fediboat.api.timelines import (
    APIClient,
    HomeTimelineAPI,
    NotificationAPI,
    PersonalAPI,
    PublicTimelineAPI,
    ThreadAPI,
    TimelineAPI,
)
from fediboat.entities import BaseEntity, Context, Notification, Status
from fediboat.settings import AuthSettings

T = TypeVar("T")
EntitySequence: TypeAlias = "Sequence[BaseEntity]"


class ResponseData(Generic[T], NamedTuple):
    json: str
    validated: T


@dataclass
class ExpectedResponse(Generic[T]):
    new: ResponseData[T]
    old: ResponseData[T]


@dataclass
class ExpectedEntityResponse(ExpectedResponse[EntitySequence]):
    pass


@dataclass
class ExpectedThreadResponse(ExpectedResponse[Context]):
    status: Status


@pytest.fixture
def statuses_validator() -> TypeAdapter[list[Status]]:
    return TypeAdapter(list[Status])


@pytest.fixture
def notifications_validator() -> TypeAdapter[list[Notification]]:
    return TypeAdapter(list[Notification])


@pytest.fixture
def expected_statuses(
    statuses_validator: TypeAdapter[list[Status]],
) -> ExpectedEntityResponse:
    with open("tests/data/statuses.json") as f:
        new_json = f.read()
    new_validated = statuses_validator.validate_json(new_json)

    with open("tests/data/old_statuses.json") as f:
        old_json = f.read()
    old_validated = statuses_validator.validate_json(old_json)

    return ExpectedEntityResponse(
        ResponseData(new_json, new_validated),
        ResponseData(old_json, old_validated),
    )


@pytest.fixture
def expected_notifications(
    notifications_validator: TypeAdapter[list[Notification]],
) -> ExpectedEntityResponse:
    with open("tests/data/notifications.json") as f:
        new_json = f.read()
    new_validated = notifications_validator.validate_json(new_json)

    with open("tests/data/old_notifications.json") as f:
        old_json = f.read()
    old_validated = notifications_validator.validate_json(old_json)

    return ExpectedEntityResponse(
        ResponseData(new_json, new_validated),
        ResponseData(old_json, old_validated),
    )


@pytest.fixture
def expected_thread() -> ExpectedThreadResponse:
    with open("tests/data/new_thread_statuses.json") as f:
        new_json = f.read()
    new_validated = Context.model_validate_json(new_json)

    with open("tests/data/old_thread_statuses.json") as f:
        old_json = f.read()
    old_validated = Context.model_validate_json(old_json)

    with open("tests/data/thread_status.json") as f:
        thread_status = Status.model_validate_json(f.read())

    return ExpectedThreadResponse(
        ResponseData(
            new_json,
            new_validated,
        ),
        ResponseData(
            old_json,
            old_validated,
        ),
        thread_status,
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
    "timeline_api_cls,expected_entities_fixture",
    [
        (HomeTimelineAPI, "expected_statuses"),
        (PublicTimelineAPI, "expected_statuses"),
        (PersonalAPI, "expected_statuses"),
        (NotificationAPI, "expected_notifications"),
    ],
)
def test_timeline_api(
    timeline_api_cls: type[TimelineAPI[BaseEntity]],
    expected_entities_fixture: str,
    settings: AuthSettings,
    monkeypatch: pytest.MonkeyPatch,
    request: pytest.FixtureRequest,
):
    expected_response: ExpectedEntityResponse = request.getfixturevalue(
        expected_entities_fixture
    )

    get_request_mock = MagicMock(return_value=expected_response.new.json)
    client_mock = MagicMock(spec_set=APIClient, get=get_request_mock)
    timeline_api = timeline_api_cls(settings=settings, client=client_mock)

    response_entities = timeline_api.fetch_new()
    get_request_mock.assert_called_with(timeline_api.api_endpoint)
    assert len(response_entities) == 1
    assert len(expected_response.new.validated) == 1
    assert response_entities[0] == expected_response.new.validated[0]

    get_request_mock.return_value = expected_response.old.json
    response_entities = timeline_api.fetch_old()
    get_request_mock.assert_called_with(
        timeline_api.api_endpoint,
        max_id=response_entities[0].id,
    )
    assert len(response_entities) == 2

    response_entities = timeline_api.fetch_new()
    get_request_mock.assert_called_with(timeline_api.api_endpoint)
    assert len(response_entities) == 1


def test_thread_api(expected_thread: ExpectedThreadResponse, settings: AuthSettings):
    get_request_mock = MagicMock(return_value=expected_thread.old.json)
    client_mock = MagicMock(spec_set=APIClient, get=get_request_mock)
    thread_api = ThreadAPI(
        settings=settings, status=expected_thread.status, client=client_mock
    )

    statuses = thread_api.fetch_new()
    assert statuses[0] == expected_thread.old.validated.ancestors[0]
    assert statuses[1] == expected_thread.status
    assert statuses[2] == expected_thread.old.validated.descendants[0]

    get_request_mock.return_value = expected_thread.new.json
    statuses = thread_api.fetch_new()
    assert statuses[0] == expected_thread.new.validated.ancestors[0]
    assert statuses[1] == expected_thread.status
    assert statuses[2:] == expected_thread.new.validated.descendants
