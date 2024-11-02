from typing import NamedTuple, Sequence
from unittest.mock import MagicMock
import pytest

from pydantic import TypeAdapter
from fediboat.api.timelines import (
    APIClient,
    HomeTimelineAPI,
    PersonalAPI,
    PublicTimelineAPI,
    TimelineAPI,
    ThreadAPI,
    NotificationAPI,
)
from fediboat.entities import BaseEntity, Notification, Status
from fediboat.settings import AuthSettings


class ExpectedResponse(NamedTuple):
    new_json: str
    new_validated: Sequence[BaseEntity]
    old_json: str
    old_validated: Sequence[BaseEntity]


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
        new_statuses_json = f.read()
    new_statuses_validated = statuses_validator.validate_json(new_statuses_json)

    with open("tests/data/old_statuses.json") as f:
        old_statuses_json = f.read()
    old_statuses_validated = statuses_validator.validate_json(old_statuses_json)

    return ExpectedResponse(
        new_statuses_json,
        new_statuses_validated,
        old_statuses_json,
        old_statuses_validated,
    )


@pytest.fixture
def expected_notifications(
    notifications_validator: TypeAdapter[list[Notification]],
) -> ExpectedResponse:
    with open("tests/data/notifications.json") as f:
        new_notifications_json = f.read()
    new_notifications_validated = notifications_validator.validate_json(
        new_notifications_json
    )

    with open("tests/data/old_notifications.json") as f:
        old_notifications_json = f.read()
    old_notifications_validated = notifications_validator.validate_json(
        old_notifications_json
    )

    return ExpectedResponse(
        new_notifications_json,
        new_notifications_validated,
        old_notifications_json,
        old_notifications_validated,
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
    expected_response: ExpectedResponse = request.getfixturevalue(
        expected_entities_fixture
    )

    get_request_mock = MagicMock(return_value=expected_response.new_json)
    client_mock = MagicMock(spec_set=APIClient, get=get_request_mock)
    timeline_api = timeline_api_cls(settings=settings, client=client_mock)

    response_entities = timeline_api.fetch_new()
    get_request_mock.assert_called_with(timeline_api.api_endpoint)
    assert len(response_entities) == 1
    assert len(expected_response.new_validated) == 1
    assert response_entities[0] == expected_response.new_validated[0]

    get_request_mock.return_value = expected_response.old_json
    response_entities = timeline_api.fetch_old()
    get_request_mock.assert_called_with(
        timeline_api.api_endpoint,
        max_id=response_entities[0].id,
    )
    assert len(response_entities) == 2

    response_entities = timeline_api.fetch_new()
    get_request_mock.assert_called_with(timeline_api.api_endpoint)
    assert len(response_entities) == 1
