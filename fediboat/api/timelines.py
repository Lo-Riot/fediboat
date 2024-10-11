from abc import ABC, abstractmethod
from typing import Generic, TypeAlias, TypeVar
from pydantic import TypeAdapter

import requests

from fediboat.api.auth import get_headers
from fediboat.settings import AuthSettings
from fediboat.entities import BaseEntity, Context, Notification, Status

Entity = TypeVar("Entity", bound=BaseEntity)
QueryParams: TypeAlias = str | int | bool


class BaseAPI(Generic[Entity], ABC):
    """Provides basic functionality for an authenticated user to work with Mastodon API"""

    def __init__(self, settings: AuthSettings):
        self.settings = settings
        self.headers = get_headers(settings.access_token)
        self.entities: list[Entity] = list()

    def _fetch_entities(self, api_endpoint: str, **query_params: QueryParams) -> str:
        return requests.get(
            self.settings.instance_url + api_endpoint,
            params=query_params,
            headers=self.headers,
        ).text

    def get_entity(self, index: int) -> Entity:
        return self.entities[index]

    @abstractmethod
    def fetch_new(self) -> list[Entity]:
        """Returns new entities"""


class TimelineAPI(BaseAPI[Entity]):
    def __init__(
        self,
        settings: AuthSettings,
        validator: TypeAdapter[list[Entity]],
        api_endpoint: str = "/api/v1/timelines/home",
    ):
        self.api_endpoint = api_endpoint
        self.validator = validator
        super().__init__(settings)

    def _get_query_params(self, **query_params: QueryParams) -> dict[str, QueryParams]:
        """Return a new dict of query parameters.
        Override it to add custom parameters."""
        return query_params

    def fetch_new(self) -> list[Entity]:
        """Refresh the timeline, return the latest entities."""

        query_params = self._get_query_params()
        new_statuses_json = self._fetch_entities(self.api_endpoint, **query_params)
        new_statuses = self.validator.validate_json(new_statuses_json)
        if len(new_statuses) == 0:
            return self.entities

        self.entities = new_statuses
        return self.entities

    def fetch_old(self) -> list[Entity]:
        """Return the next page of entities."""

        query_params = self._get_query_params()
        if len(self.entities) != 0:
            query_params["max_id"] = self.entities[-1].id

        new_statuses_json = self._fetch_entities(self.api_endpoint, **query_params)
        new_statuses = self.validator.validate_json(new_statuses_json)
        self.entities.extend(new_statuses)
        return self.entities


class PublicTimelineAPI(TimelineAPI[Status]):
    def __init__(self, settings: AuthSettings):
        super().__init__(
            settings,
            validator=TypeAdapter(list[Status]),
            api_endpoint="/api/v1/timelines/public",
        )


class PublicRemoteTimelineAPI(PublicTimelineAPI):
    def _get_query_params(self, **query_params: QueryParams) -> dict[str, QueryParams]:
        query_params["remote"] = True
        return super()._get_query_params(**query_params)


class LocalTimelineAPI(PublicTimelineAPI):
    def _get_query_params(self, **query_params: QueryParams) -> dict[str, QueryParams]:
        query_params["local"] = True
        return super()._get_query_params(**query_params)


class NotificationAPI(TimelineAPI[Notification]):
    def __init__(self, settings: AuthSettings):
        super().__init__(
            settings,
            validator=TypeAdapter(list[Notification]),
            api_endpoint="/api/v1/notifications",
        )

    def _get_query_params(self, **query_params: QueryParams) -> dict[str, QueryParams]:
        query_params["limit"] = 20
        return super()._get_query_params(**query_params)


class ThreadAPI(BaseAPI[Status]):
    def __init__(
        self,
        settings: AuthSettings,
        status: Status,
    ):
        self.status = status
        super().__init__(settings)

    def fetch_new(self) -> list[Status]:
        thread_context_json = self._fetch_entities(
            f"/api/v1/statuses/{self.status.id}/context"
        )
        thread_context = Context.model_validate_json(thread_context_json)

        thread = thread_context.ancestors.copy()
        thread.append(self.status)
        thread.extend(thread_context.descendants)

        self.entities = thread
        return self.entities


class PersonalAPI(TimelineAPI[Status]):
    def __init__(self, settings: AuthSettings):
        super().__init__(
            settings,
            TypeAdapter(list[Status]),
            f"/api/v1/accounts/{settings.id}/statuses",
        )
