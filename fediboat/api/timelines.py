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

        if resp.links.get("next"):
            self._next_link = resp.links["next"]["url"]
            log("Next link:", self._next_link)
        return resp.text

    def get_next(self) -> str:
        # TODO: Handle exception if _next_link == ''
        return self.get(self._next_link)


class BaseAPI(Generic[Entity], ABC):
    """Provides basic functionality for an authenticated user to work with Mastodon API"""

    def __init__(self, settings: AuthSettings, client: APIClient | None = None):
        self.settings = settings
        self.entities: list[Entity] = list()
        self.client = client

    @property
    def client(self):
        if self._client is None:
            raise ValueError("Client is not set.")
        return self._client

    @client.setter
    def client(self, value: APIClient | None):
        if value is None:
            value = APIClient(self.settings)
        self._client = value

    def get_entity(self, index: int) -> Entity:
        return self.entities[index]

    @abstractmethod
    def fetch_new(self) -> list[Entity]:
        """Returns new entities"""


class TimelineAPI(BaseAPI[Entity]):
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
        self.entities.extend(new_statuses)
        return self.entities


class HomeTimelineAPI(TimelineAPI[Status]):
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


class PublicTimelineAPI(TimelineAPI[Status]):
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


class NotificationAPI(TimelineAPI[Notification]):
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


class ThreadAPI(BaseAPI[Status]):
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


class PersonalAPI(TimelineAPI[Status]):
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


class BookmarksAPI(TimelineAPI[Status]):
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
