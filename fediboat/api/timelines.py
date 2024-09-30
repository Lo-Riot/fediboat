from abc import ABC, abstractmethod
from typing import TypeVar
from pydantic import TypeAdapter, BaseModel

import requests
from textual import log

from fediboat.api.auth import get_headers
from fediboat.settings import AuthSettings
from fediboat.entities import Context, Status

T = TypeVar("T", bound=BaseModel)


class BaseAPI[T](ABC):
    """Provides basic functionality for an authenticated user to work with Mastodon API"""

    def __init__(self, settings: AuthSettings):
        self.settings = settings
        self.headers = get_headers(settings.access_token)
        self._entities: list[T] = list()

    def _fetch_entities(
        self, api_endpoint: str, query_params: dict | None = None
    ) -> str:
        return requests.get(
            self.settings.instance_url + api_endpoint,
            params=query_params,
            headers=self.headers,
        ).text

    def get_entity(self, index: int) -> T:
        return self._entities[index]

    @abstractmethod
    def fetch_new(self) -> list[T]:
        """Returns new entities"""  # TODO: Add max statuses limit and clear the old ones


class TimelineAPI(BaseAPI[Status]):
    def __init__(
        self, settings: AuthSettings, api_endpoint: str = "/api/v1/timelines/home"
    ):
        self.api_endpoint = api_endpoint
        self.statuses_validator = TypeAdapter(list[Status])
        super().__init__(settings)

    def _get_query_params(self, query_params: dict | None = None) -> dict:
        if query_params is None:
            query_params = dict()
        return query_params

    def fetch_new(self) -> list[Status]:
        """Returns previous page"""
        query_params = self._get_query_params()
        if len(self._entities) != 0:
            query_params["min_id"] = self._entities[0].id

        new_statuses_json = self._fetch_entities(self.api_endpoint, query_params)
        new_statuses = self.statuses_validator.validate_json(new_statuses_json)
        new_statuses.extend(self._entities)

        self._entities = new_statuses
        return self._entities

    def fetch_old(self) -> list[Status]:
        """Returns next page"""
        query_params = self._get_query_params()
        if len(self._entities) != 0:
            query_params["max_id"] = self._entities[-1].id

        new_statuses_json = self._fetch_entities(self.api_endpoint, query_params)
        new_statuses = self.statuses_validator.validate_json(new_statuses_json)
        self._entities.extend(new_statuses)
        return self._entities


class PublicTimelineAPI(TimelineAPI):
    def __init__(self, settings: AuthSettings):
        super().__init__(settings, api_endpoint="/api/v1/timelines/public")


class PublicRemoteTimelineAPI(PublicTimelineAPI):
    def _get_query_params(self, query_params: dict | None = None) -> dict:
        if query_params is None:
            query_params = dict()

        query_params["remote"] = True
        return super()._get_query_params(query_params)


class LocalTimelineAPI(PublicTimelineAPI):
    def _get_query_params(self, query_params: dict | None = None) -> dict:
        if query_params is None:
            query_params = dict()

        query_params["local"] = True
        return super()._get_query_params(query_params)


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

        self._entities = thread
        return self._entities
