import json
from unittest.mock import MagicMock

import pytest
from pydantic import TypeAdapter
from requests import Session

from fediboat.api.timelines import (
    context_to_entities,
    notifications_to_entities,
    statuses_to_entities,
)
from fediboat.entities import Context, Notification, Status
from fediboat.settings import AuthSettings
from tests.test_api import ExpectedResponse, ExpectedThreadResponse, ResponseData


@pytest.fixture(scope="session")
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


@pytest.fixture(scope="module")
def session() -> MagicMock:
    response_mock = MagicMock()
    get_request_mock = MagicMock(return_value=response_mock)
    session_mock = MagicMock(spec_set=Session, get=get_request_mock)
    return session_mock


@pytest.fixture(scope="session")
def statuses_validator() -> TypeAdapter[list[Status]]:
    return TypeAdapter(list[Status])


@pytest.fixture(scope="session")
def notifications_validator() -> TypeAdapter[list[Notification]]:
    return TypeAdapter(list[Notification])


@pytest.fixture(scope="session")
def expected_statuses(
    statuses_validator: TypeAdapter[list[Status]],
) -> ExpectedResponse:
    with open("tests/data/statuses.json") as f:
        new_json = json.load(f)
    new_statuses = statuses_validator.validate_python(new_json)
    new_entities = statuses_to_entities(new_statuses)

    with open("tests/data/old_statuses.json") as f:
        old_json = json.load(f)
    old_statuses = statuses_validator.validate_python(old_json)
    old_entities = statuses_to_entities(old_statuses)

    return ExpectedResponse(
        ResponseData(new_json, new_entities),
        ResponseData(old_json, old_entities),
    )


@pytest.fixture(scope="session")
def expected_notifications(
    notifications_validator: TypeAdapter[list[Notification]],
) -> ExpectedResponse:
    with open("tests/data/notifications.json") as f:
        new_json = json.load(f)
    new_notifications = notifications_validator.validate_python(new_json)
    new_entities = notifications_to_entities(new_notifications)

    with open("tests/data/old_notifications.json") as f:
        old_json = json.load(f)
    old_notifications = notifications_validator.validate_python(old_json)
    old_entities = notifications_to_entities(old_notifications)

    return ExpectedResponse(
        ResponseData(new_json, new_entities),
        ResponseData(old_json, old_entities),
    )


@pytest.fixture(scope="session")
def expected_thread() -> ExpectedThreadResponse:
    with open("tests/data/thread_status.json") as f:
        thread_status = Status.model_validate_json(f.read())

    with open("tests/data/new_thread_statuses.json") as f:
        new_json = json.load(f)
    new_context = Context.model_validate(new_json)
    new_entities = context_to_entities(new_context, thread_status)

    with open("tests/data/old_thread_statuses.json") as f:
        old_json = json.load(f)
    old_context = Context.model_validate(old_json)
    old_entities = context_to_entities(old_context, thread_status)

    return ExpectedThreadResponse(
        ResponseData(
            new_json,
            new_entities,
        ),
        ResponseData(
            old_json,
            old_entities,
        ),
        thread_status,
    )
