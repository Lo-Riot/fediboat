from typing import Callable, Generator, Sequence, TypeAlias, TypeVar
from urllib.parse import urlencode, urlparse

from bs4 import BeautifulSoup
from pydantic import TypeAdapter
from requests import Response, Session, codes
from textual import log

from fediboat.api.auth import APIError
from fediboat.entities import (
    Context,
    EntityProtocol,
    Notification,
    Status,
    TUIEntity,
)
from fediboat.settings import AuthSettings, Config

TimelineCallable: TypeAlias = Callable[
    [Session, AuthSettings], Generator[list[TUIEntity]]
]
Entity = TypeVar("Entity", bound=EntityProtocol)
QueryParams: TypeAlias = str | int | bool | Sequence[str]


def get_timelines(config: Config) -> dict[str, TimelineCallable]:
    return {
        "Home": home_timeline_generator,
        "Local": local_timeline_generator,
        "Global": global_timeline_generator,
        "Notifications": get_notifications_timeline(config),
        "Personal": personal_timeline_generator,
        "Bookmarks": bookmarks_timeline_generator,
    }


def handle_request_errors(resp: Response, *args, **kwargs):
    if resp.status_code != codes.ok:
        resp_json = resp.json()
        raise APIError(
            f"Endpoint: {urlparse(resp.url).path}\nError: {resp_json["error"]}"
        )


def _html_to_plain_text(status: Status) -> Status:
    soup = BeautifulSoup(status.content, "html.parser")
    log("id:", status.id)
    log(f"html:\n{soup.prettify()}")

    for element in soup.find_all("br"):
        element.replace_with("  \n")

    plain_text = ""
    for element in soup.find_all("p"):
        plain_text += element.get_text() + "\n\n"

    if not plain_text:
        plain_text = soup.get_text()

    log("plain text:", repr(plain_text))
    return status.model_copy(update={"content": plain_text})


def _timeline_generator(
    session: Session,
    api_endpoint: str,
    validator: TypeAdapter[list[Entity]],
    **query_params: QueryParams,
) -> Generator[list[Entity]]:
    next_url: str = f"{api_endpoint}?{urlencode(query_params, doseq=True)}"
    while next_url:
        resp = session.get(next_url)
        resp_json = resp.json()
        yield validator.validate_python(resp_json)

        if resp.links.get("next") is None or resp.links["next"]["url"] == next_url:
            return

        next_url = resp.links["next"]["url"]


def status_to_entity(status: Status) -> TUIEntity:
    if status.reblog is not None:
        cleaned_status = _html_to_plain_text(status.reblog)
    else:
        cleaned_status = _html_to_plain_text(status)

    return TUIEntity(
        status=cleaned_status,
        author=status.account.acct,
    )


def statuses_to_entities(statuses: list[Status]) -> list[TUIEntity]:
    return [status_to_entity(status) for status in statuses]


def notifications_to_entities(notifications: list[Notification]) -> list[TUIEntity]:
    entities: list[TUIEntity] = []
    for notification in notifications:
        cleaned_status = None
        if notification.status is not None:
            cleaned_status = _html_to_plain_text(notification.status)

        entities.append(
            TUIEntity(
                status=cleaned_status,
                author=notification.account.acct,
                notification_type=notification.type,
            )
        )
    return entities


def context_to_entities(context: Context, status: Status) -> list[TUIEntity]:
    ancestors = statuses_to_entities(context.ancestors)
    descendants = statuses_to_entities(context.descendants)
    return ancestors + [status_to_entity(status)] + descendants


def status_timeline_generator(
    session: Session, api_endpoint: str, **query_params: QueryParams
) -> Generator[list[TUIEntity]]:
    for statuses in _timeline_generator(
        session, api_endpoint, TypeAdapter(list[Status]), **query_params
    ):
        yield statuses_to_entities(statuses)


def notification_timeline_generator(
    session: Session, api_endpoint: str, **query_params: QueryParams
) -> Generator[list[TUIEntity]]:
    for notifications in _timeline_generator(
        session, api_endpoint, TypeAdapter(list[Notification]), **query_params
    ):
        yield notifications_to_entities(notifications)


def home_timeline_generator(
    session: Session, settings: AuthSettings
) -> Generator[list[TUIEntity]]:
    return status_timeline_generator(
        session, f"{settings.instance_url}/api/v1/timelines/home"
    )


def local_timeline_generator(
    session: Session, settings: AuthSettings
) -> Generator[list[TUIEntity]]:
    return status_timeline_generator(
        session, f"{settings.instance_url}/api/v1/timelines/public", local=True
    )


def global_timeline_generator(
    session: Session, settings: AuthSettings
) -> Generator[list[TUIEntity]]:
    return status_timeline_generator(
        session, f"{settings.instance_url}/api/v1/timelines/public", remote=True
    )


def personal_timeline_generator(
    session: Session, settings: AuthSettings
) -> Generator[list[TUIEntity]]:
    return status_timeline_generator(
        session, f"{settings.instance_url}/api/v1/accounts/{settings.id}/statuses"
    )


def bookmarks_timeline_generator(
    session: Session, settings: AuthSettings
) -> Generator[list[TUIEntity]]:
    return status_timeline_generator(
        session, f"{settings.instance_url}/api/v1/bookmarks"
    )


def get_notifications_timeline(
    config: Config,
) -> Callable[[Session, AuthSettings], Generator[list[TUIEntity]]]:
    def notifications_timeline_generator(
        session: Session, settings: AuthSettings
    ) -> Generator[list[TUIEntity]]:
        params: dict[str, QueryParams] = {
            "types[]": config.notifications.show,
            "limit": 20,
        }
        return notification_timeline_generator(
            session, f"{settings.instance_url}/api/v1/notifications", **params
        )

    return notifications_timeline_generator


def thread_fetcher(
    session: Session, settings: AuthSettings, status: Status
) -> Callable[..., list[TUIEntity]]:
    def fetch_thread() -> list[TUIEntity]:
        resp = session.get(
            f"{settings.instance_url}/api/v1/statuses/{status.id}/context"
        )
        resp_json = resp.json()
        context = Context.model_validate(resp_json)
        return context_to_entities(context, status)

    return fetch_thread


def favourite_status(
    session: Session, settings: AuthSettings, status: Status
) -> Status:
    endpoint = "favourite" if not status.favourited else "unfavourite"
    resp = session.post(
        f"{settings.instance_url}/api/v1/statuses/{status.id}/{endpoint}"
    )
    return Status.model_validate(resp.json())


def reblog_status(session: Session, settings: AuthSettings, status: Status) -> Status:
    endpoint = "reblog" if not status.reblogged else "unreblog"
    resp = session.post(
        f"{settings.instance_url}/api/v1/statuses/{status.id}/{endpoint}"
    )
    return Status.model_validate(resp.json())


def post_status(
    content: str,
    session: Session,
    settings: AuthSettings,
    in_reply_to_id: str | None = None,
    visibility: str = "public",
) -> Status:
    resp = session.post(
        f"{settings.instance_url}/api/v1/statuses",
        data={
            "status": content,
            "in_reply_to_id": in_reply_to_id,
            "visibility": visibility,
        },
    )
    resp_json = resp.json()
    return Status.model_validate(resp_json)
