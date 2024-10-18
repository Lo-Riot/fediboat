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


@pytest.fixture
def statuses_validator() -> TypeAdapter[list[Status]]:
    return TypeAdapter(list[Status])


@pytest.fixture
def notifications_validator() -> TypeAdapter[list[Notification]]:
    return TypeAdapter(list[Notification])


@pytest.fixture
def expected_statuses(
    statuses_validator: TypeAdapter[list[Status]],
) -> tuple[str, list[Status]]:
    with open("tests/data/statuses.json") as f:
        response_mock = f.read()
    return response_mock, statuses_validator.validate_json(response_mock)


@pytest.fixture
def expected_notifications(
    notifications_validator: TypeAdapter[list[Notification]],
) -> tuple[str, list[Notification]]:
    with open("tests/data/notifications.json") as f:
        response_mock = f.read()
    return response_mock, notifications_validator.validate_json(response_mock)


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
    expected_entities: tuple[str, list[BaseEntity]] = request.getfixturevalue(
        expected_entities_fixture
    )
    expected_json_entities, expected_validated_entities = expected_entities

    get_request_mock = MagicMock(return_value=expected_json_entities)
    client_mock = MagicMock(spec_set=APIClient, get=get_request_mock)
    timeline_api = timeline_api_cls(settings=settings, client=client_mock)

    response_entities = timeline_api.fetch_new()
    get_request_mock.assert_called_with(timeline_api.api_endpoint)
    assert len(response_entities) == 1
    assert len(expected_validated_entities) == 1
    assert response_entities[0] == expected_validated_entities[0]

    response_entities = timeline_api.fetch_old()
    get_request_mock.assert_called_with(
        timeline_api.api_endpoint,
        max_id=response_entities[0].id,
    )
    assert len(response_entities) == 2

    response_entities = timeline_api.fetch_new()
    get_request_mock.assert_called_with(timeline_api.api_endpoint)
    assert len(response_entities) == 1
