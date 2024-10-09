from pydantic import TypeAdapter
import pytest
from fediboat.api.timelines import QueryParams, TimelineAPI, ThreadAPI, NotificationAPI
from fediboat.entities import Status
from fediboat.settings import AuthSettings


class TimelineAPIMock(TimelineAPI[Status]):
    def __init__(
        self,
        settings: AuthSettings,
        validator: TypeAdapter[list[Status]],
        response_mock: str,
    ):
        self._response_mock = response_mock
        super().__init__(settings, validator)

    def _fetch_entities(self, api_endpoint: str, **query_params: QueryParams) -> str:
        return self._response_mock


class ThreadAPIMock(ThreadAPI):
    def __init__(
        self,
        settings: AuthSettings,
        status: Status,
        response_mock: str,
    ):
        self._response_mock = response_mock
        super().__init__(settings, status)

    def _fetch_entities(self, api_endpoint: str, **query_params: QueryParams) -> str:
        return self._response_mock


class NotificationAPIMock(NotificationAPI):
    def __init__(
        self,
        settings: AuthSettings,
        response_mock: str,
    ):
        self._response_mock = response_mock
        super().__init__(settings)

    def _fetch_entities(self, api_endpoint: str, **query_params: QueryParams) -> str:
        return self._response_mock


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


@pytest.fixture
def home_api(
    settings: AuthSettings,
    timeline_statuses: str,
    statuses_validator: TypeAdapter[list[Status]],
) -> TimelineAPIMock:
    return TimelineAPIMock(settings, statuses_validator, timeline_statuses)


def test_home_api(
    home_api: TimelineAPIMock,
    timeline_statuses: str,
    statuses_validator: TypeAdapter[list[Status]],
):
    expected_statuses = statuses_validator.validate_json(timeline_statuses)
    statuses = home_api.fetch_new()

    assert len(expected_statuses) == 1
    assert len(statuses) == 1
    assert statuses[0] == expected_statuses[0]
