from unittest.mock import MagicMock
import pytest

from pydantic import TypeAdapter
from fediboat.api.timelines import (
    StatusTimelineAPI,
    PersonalAPI,
    PublicTimelineAPI,
    QueryParams,
    TimelineAPI,
    ThreadAPI,
    NotificationAPI,
)
from fediboat.entities import Status
from fediboat.settings import AuthSettings


@pytest.fixture
def statuses_validator() -> TypeAdapter[list[Status]]:
    return TypeAdapter(list[Status])


@pytest.fixture
def expected_statuses(
    statuses_validator: TypeAdapter[list[Status]],
) -> tuple[str, list[Status]]:
    with open("tests/data/statuses.json") as f:
        response_mock = f.read()
    return response_mock, statuses_validator.validate_json(response_mock)


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
    "timeline_api_cls,api_endpoint,query_params",
    [
        (StatusTimelineAPI, "/api/v1/timelines/home", {}),
        (PublicTimelineAPI, "/api/v1/timelines/public", {"local": True}),
        (PublicTimelineAPI, "/api/v1/timelines/public", {"remote": True}),
    ],
)
def test_status_timelines(
    timeline_api_cls: type[StatusTimelineAPI],
    api_endpoint: str,
    query_params: dict[str, QueryParams],
    expected_statuses: tuple[str, list[Status]],
    settings: AuthSettings,
    monkeypatch: pytest.MonkeyPatch,
):
    expected_json_statuses, expected_validated_statuses = expected_statuses
    timeline_api = timeline_api_cls(settings, api_endpoint, **query_params)

    mock_api_response = MagicMock(return_value=expected_json_statuses)
    monkeypatch.setattr(timeline_api, "_fetch_entities", mock_api_response)
    response_statuses = timeline_api.fetch_new()

    mock_api_response.assert_called_with(api_endpoint, **query_params)
    assert len(response_statuses) == 1
    assert len(expected_validated_statuses) == 1
    assert response_statuses[0] == expected_validated_statuses[0]
