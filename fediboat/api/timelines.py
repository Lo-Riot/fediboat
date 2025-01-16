from typing import Callable, Generator, Sequence, TypeAlias, TypeVar
from urllib.parse import urlencode

from pydantic import TypeAdapter
from requests import Session

from fediboat.entities import (
    Context,
    EntityProtocol,
    Notification,
    Status,
    TUIEntity,
)
from fediboat.settings import AuthSettings, Config

Entity = TypeVar("Entity", bound=EntityProtocol)
QueryParams: TypeAlias = str | int | bool | Sequence[str]


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
    return TUIEntity(
        id=status.id,
        content=status.content,
        author=status.account.acct,
        created_at=status.created_at,
        in_reply_to_id=status.in_reply_to_id,
    )


def statuses_to_entities(statuses: list[Status]) -> list[TUIEntity]:
    return [status_to_entity(status) for status in statuses]


def notifications_to_entities(notifications: list[Notification]) -> list[TUIEntity]:
    entities: list[TUIEntity] = []
    for notification in notifications:
        id = content = in_reply_to_id = None

        if notification.status is not None:
            id = notification.status.id
            content = notification.status.content
            in_reply_to_id = notification.status.in_reply_to_id

        entities.append(
            TUIEntity(
                id=id,
                content=content,
                author=notification.account.acct,
                created_at=notification.created_at,
                in_reply_to_id=in_reply_to_id,
                notification_type=notification.type,
            )
        )
    return entities


def context_to_entities(context: Context, status: TUIEntity) -> list[TUIEntity]:
    ancestors = statuses_to_entities(context.ancestors)
    descendants = statuses_to_entities(context.descendants)
    return ancestors + [status] + descendants


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
    session: Session, settings: AuthSettings, status: TUIEntity
) -> Callable[..., list[TUIEntity]]:
    def fetch_thread() -> list[TUIEntity]:
        context_json = session.get(
            f"{settings.instance_url}/api/v1/statuses/{status.id}/context"
        ).json()
        context = Context.model_validate(context_json)
        return context_to_entities(context, status)

    return fetch_thread


def post_status(content: str, session: Session, settings: AuthSettings) -> Status:
    status = session.post(
        f"{settings.instance_url}/api/v1/statuses",
        data={"status": content},
    )
    return Status.model_validate(status.json())
