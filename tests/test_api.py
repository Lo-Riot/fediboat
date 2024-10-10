from unittest.mock import MagicMock
import pytest

from pydantic import TypeAdapter
from fediboat.api.timelines import QueryParams, TimelineAPI, ThreadAPI, NotificationAPI
from fediboat.entities import Status
from fediboat.settings import AuthSettings


@pytest.fixture
def statuses_validator() -> TypeAdapter[list[Status]]:
    return TypeAdapter(list[Status])


@pytest.fixture
def timeline_statuses() -> str:
    with open("tests/data/timeline_statuses.json") as f:
        response_mock = f.read()
    return response_mock


@pytest.fixture
def settings() -> AuthSettings:
    return AuthSettings(
        instance_url="http://localhost",
        instance_domain="localhost",
        full_username="test_user@localhost",
        access_token="123",
        client_id="1234",
        client_secret="12345",
    )


def test_home_api(
    timeline_statuses: str,
    settings: AuthSettings,
    statuses_validator: TypeAdapter[list[Status]],
    monkeypatch: pytest.MonkeyPatch,
):
    home_api = TimelineAPI(settings, statuses_validator)
    mock_api_response = MagicMock(return_value=timeline_statuses)
    monkeypatch.setattr(home_api, "_fetch_entities", mock_api_response)

    expected_statuses = statuses_validator.validate_json(timeline_statuses)
    statuses = home_api.fetch_new()

    # TODO: add api enpoints to the settings
    mock_api_response.assert_called_with("/api/v1/timelines/home")
    assert len(expected_statuses) == 1
    assert len(statuses) == 1
    assert statuses[0] == expected_statuses[0]
