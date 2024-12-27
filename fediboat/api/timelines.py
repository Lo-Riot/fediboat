from abc import ABC, abstractmethod
from typing import Generic, TypeAlias, TypeVar

import requests
from pydantic import TypeAdapter
from textual import log

from fediboat.api.auth import get_headers
from fediboat.entities import BaseEntity, Context, Notification, Status
from fediboat.settings import AuthSettings

Entity = TypeVar("Entity", bound=BaseEntity)
QueryParams: TypeAlias = str | int | bool


class APIClient:
    def __init__(self, settings: AuthSettings, **default_query_params: QueryParams):
        self.settings = settings
        self._default_query_params = default_query_params
        self._headers = get_headers(self.settings.access_token)
        self._next_link = ""

    def get(self, api_endpoint: str) -> str:
        resp = requests.get(
            api_endpoint,
            params=self._default_query_params,
            headers=self._headers,
        )

        if resp.links.get("next") is not None:
            self._next_link = resp.links["next"]["url"]
            log("Next link:", self._next_link)
        return resp.text

    def get_next(self) -> str:
        # TODO: Handle exception if _next_link == ''
        return self.get(self._next_link)

    def post(self, api_endpoint: str, data: dict) -> str:
        return requests.post(
            api_endpoint,
            data=data,
            headers=self._headers,
        ).text


class BaseAPI(ABC):
    def __init__(self, settings: AuthSettings, client: APIClient):
        self.settings = settings
        self.client = client


class AccountAPI(BaseAPI):
    """API for managing account and posting statuses"""

    def post_status(self, content: str) -> Status:
        status = self.client.post(
            f"{self.settings.instance_url}/api/v1/statuses",
            data={"status": content},
        )
        return Status.model_validate_json(status)


class EntityFetcher(Generic[Entity], BaseAPI):
    """API for fetching Mastodon entities"""

    def __init__(self, settings: AuthSettings, client: APIClient | None = None):
        self.entities: list[Entity] = list()
        if client is None:
            client = APIClient(settings)
        self.client = client
        super().__init__(settings, client)

    def get_entity(self, index: int) -> Entity:
        return self.entities[index]

    @abstractmethod
    def fetch_new(self) -> list[Entity]:
        """Returns new entities"""


class TimelineFetcher(EntityFetcher[Entity]):
    def __init__(
        self,
        settings: AuthSettings,
        validator: TypeAdapter[list[Entity]] = TypeAdapter(list[BaseEntity]),
        api_endpoint: str = "/api/v1/timelines/home",
        client: APIClient | None = None,
    ):
        self.api_endpoint = api_endpoint
        self.validator = validator
        super().__init__(settings, client)

    def fetch_new(self) -> list[Entity]:
        """Refresh the timeline, return the latest entities."""

        new_statuses_json = self.client.get(
            self.settings.instance_url + self.api_endpoint
        )
        new_statuses = self.validator.validate_json(new_statuses_json)
        if len(new_statuses) == 0:
            return self.entities

        self.entities = new_statuses
        return self.entities

    def fetch_old(self) -> list[Entity]:
        """Return the next page of entities."""

        new_statuses_json = self.client.get_next()
        new_statuses = self.validator.validate_json(new_statuses_json)
        if new_statuses[-1].id == self.entities[-1].id:
            return self.entities
        self.entities.extend(new_statuses)
        return self.entities


class HomeTimelineFetcher(TimelineFetcher[Status]):
    def __init__(
        self,
        settings: AuthSettings,
        validator: TypeAdapter[list[Status]] = TypeAdapter(list[Status]),
        api_endpoint: str = "/api/v1/timelines/home",
        client: APIClient | None = None,
    ):
        super().__init__(
            settings,
            validator=validator,
            api_endpoint=api_endpoint,
            client=client,
        )


class PublicTimelineFetcher(TimelineFetcher[Status]):
    def __init__(
        self,
        settings: AuthSettings,
        validator: TypeAdapter[list[Status]] = TypeAdapter(list[Status]),
        api_endpoint: str = "/api/v1/timelines/public",
        client: APIClient | None = None,
    ):
        super().__init__(
            settings,
            validator=validator,
            api_endpoint=api_endpoint,
            client=client,
        )


class NotificationFetcher(TimelineFetcher[Notification]):
    def __init__(
        self,
        settings: AuthSettings,
        validator: TypeAdapter[list[Notification]] = TypeAdapter(list[Notification]),
        api_endpoint: str = "/api/v1/notifications",
        client: APIClient | None = None,
    ):
        super().__init__(
            settings,
            validator=validator,
            api_endpoint=api_endpoint,
            client=client,
        )


class ThreadFetcher(EntityFetcher[Status]):
    def __init__(
        self,
        settings: AuthSettings,
        status: Status,
        client: APIClient | None = None,
    ):
        self.status = status
        super().__init__(settings, client)

    def fetch_new(self) -> list[Status]:
        thread_context_json = self.client.get(
            f"{self.settings.instance_url}/api/v1/statuses/{self.status.id}/context"
        )
        thread_context = Context.model_validate_json(thread_context_json)

        thread = thread_context.ancestors.copy()
        thread.append(self.status)
        thread.extend(thread_context.descendants)

        self.entities = thread
        return self.entities


class PersonalTimelineFetcher(TimelineFetcher[Status]):
    def __init__(
        self,
        settings: AuthSettings,
        validator: TypeAdapter[list[Status]] = TypeAdapter(list[Status]),
        client: APIClient | None = None,
    ):
        super().__init__(
            settings,
            validator=validator,
            api_endpoint=f"/api/v1/accounts/{settings.id}/statuses",
            client=client,
        )


class BookmarksFetcher(TimelineFetcher[Status]):
    def __init__(
        self,
        settings: AuthSettings,
        validator: TypeAdapter[list[Status]] = TypeAdapter(list[Status]),
        api_endpoint: str = "/api/v1/bookmarks",
        client: APIClient | None = None,
    ):
        super().__init__(
            settings,
            validator=validator,
            api_endpoint=api_endpoint,
            client=client,
        )
