from datetime import datetime
from typing import Callable, Generator, TypeAlias, TypeVar

import requests
from pydantic import BaseModel, TypeAdapter

from fediboat.entities import Context, EntityProtocol, Notification, Status
from fediboat.settings import AuthSettings

Entity = TypeVar("Entity", bound=EntityProtocol)
QueryParams: TypeAlias = str | int | bool


class TUIEntity(BaseModel):
    id: str | None
    content: str | None
    author: str
    created_at: datetime
    in_reply_to_id: str | None
    notification_type: str | None = None


def _timeline_generator(
    session: requests.Session,
    api_endpoint: str,
    validator: TypeAdapter[list[Entity]],
    **query_params: QueryParams,
) -> Generator[list[Entity]]:
    next_url: str = api_endpoint
    while next_url:
        resp = session.get(next_url, params=query_params)
        yield validator.validate_python(resp.json())

        if resp.links.get("next") is None or resp.links["next"]["url"] == next_url:
            return

        next_url = resp.links["next"]["url"]


def status_to_tui_entity(status: Status) -> TUIEntity:
    return TUIEntity(
        id=status.id,
        content=status.content,
        author=status.account.acct,
        created_at=status.created_at,
        in_reply_to_id=status.in_reply_to_id,
    )


def statuses_to_tui_entities(statuses: list[Status]) -> list[TUIEntity]:
    return [status_to_tui_entity(status) for status in statuses]


def notifications_to_tui_entities(notifications: list[Notification]) -> list[TUIEntity]:
    return [
        TUIEntity(
            id=notification.status.id if notification.status else None,
            content=notification.status.content if notification.status else None,
            author=notification.account.acct,
            created_at=notification.created_at,
            in_reply_to_id=notification.status.in_reply_to_id
            if notification.status
            else None,
            notification_type=notification.type,
        )
        for notification in notifications
    ]


def context_to_tui_entities(context: Context, status: TUIEntity) -> list[TUIEntity]:
    ancestors = statuses_to_tui_entities(context.ancestors)
    descendants = statuses_to_tui_entities(context.descendants)
    return ancestors + [status] + descendants


def status_timeline_generator(
    session: requests.Session, api_endpoint: str, **query_params: QueryParams
) -> Generator[list[TUIEntity]]:
    for statuses in _timeline_generator(
        session, api_endpoint, TypeAdapter(list[Status]), **query_params
    ):
        yield statuses_to_tui_entities(statuses)


def notification_timeline_generator(
    session: requests.Session, api_endpoint: str, **query_params: QueryParams
) -> Generator[list[TUIEntity]]:
    for notifications in _timeline_generator(
        session, api_endpoint, TypeAdapter(list[Notification]), **query_params
    ):
        yield notifications_to_tui_entities(notifications)


def home_timeline_generator(
    session: requests.Session, settings: AuthSettings
) -> Generator[list[TUIEntity]]:
    return status_timeline_generator(
        session, f"{settings.instance_url}/api/v1/timelines/home"
    )


def local_timeline_generator(
    session: requests.Session, settings: AuthSettings
) -> Generator[list[TUIEntity]]:
    return status_timeline_generator(
        session, f"{settings.instance_url}/api/v1/timelines/public", local=True
    )


def global_timeline_generator(
    session: requests.Session, settings: AuthSettings
) -> Generator[list[TUIEntity]]:
    return status_timeline_generator(
        session, f"{settings.instance_url}/api/v1/timelines/public", remote=True
    )


def personal_timeline_generator(
    session: requests.Session, settings: AuthSettings
) -> Generator[list[TUIEntity]]:
    return status_timeline_generator(
        session, f"{settings.instance_url}/api/v1/accounts/{settings.id}/statuses"
    )


def bookmarks_timeline_generator(
    session: requests.Session, settings: AuthSettings
) -> Generator[list[TUIEntity]]:
    return status_timeline_generator(
        session, f"{settings.instance_url}/api/v1/bookmarks"
    )


def notifications_timeline_generator(
    session: requests.Session, settings: AuthSettings
) -> Generator[list[TUIEntity]]:
    return notification_timeline_generator(
        session, f"{settings.instance_url}/api/v1/notifications", limit=20
    )


def thread_fetcher(
    session: requests.Session, settings: AuthSettings, status: TUIEntity
) -> Callable[..., list[TUIEntity]]:
    def fetch_thread() -> list[TUIEntity]:
        context_json = session.get(
            f"{settings.instance_url}/api/v1/statuses/{status.id}/context"
        ).json()
        context = Context.model_validate(context_json)
        return context_to_tui_entities(context, status)

    return fetch_thread


def post_status(
    content: str, session: requests.Session, settings: AuthSettings
) -> Status:
    status = session.post(
        f"{settings.instance_url}/api/v1/statuses",
        data={"status": content},
    )
    return Status.model_validate(status.json())
