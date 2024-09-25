from abc import abstractmethod
from typing import TypeVar
from pydantic import TypeAdapter, BaseModel

import requests
from textual import log

from fediboat.api.account import BaseAPI
from fediboat.settings import AuthSettings
from fediboat.entities import Context, Status

T = TypeVar("T", bound=BaseModel)


class EntityAPI[T](BaseAPI):
    """Provides basic functionality to work with Mastodon API entities"""

    def __init__(self, settings: AuthSettings):
        self._entities: list[T] = list()
        super().__init__(settings)

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
    def update(self) -> list[T]:
        """Updates entities"""  # TODO: Add max statuses limit and clear the old ones


class TimelineAPI(EntityAPI[Status]):
    def __init__(
        self, settings: AuthSettings, api_endpoint: str = "/api/v1/timelines/home"
    ):
        self.api_endpoint = api_endpoint
        self.statuses_validator = TypeAdapter(list[Status])
        super().__init__(settings)

    def update(self, query_params: dict = dict()) -> list[Status]:
        if len(self._entities) != 0:
            since_id = self._entities[0].id
            query_params["since_id"] = since_id

        new_statuses_json = self._fetch_entities(self.api_endpoint, query_params)
        new_statuses = self.statuses_validator.validate_json(new_statuses_json)
        new_statuses.extend(self._entities)

        self._entities = new_statuses
        return self._entities


class PublicTimelineAPI(TimelineAPI):
    def __init__(self, settings: AuthSettings):
        super().__init__(settings, api_endpoint="/api/v1/timelines/public")


class PublicRemoteTimelineAPI(PublicTimelineAPI):
    def update(self, query_params: dict = dict()) -> list[Status]:
        query_params["remote"] = True
        return super().update(query_params)


class LocalTimelineAPI(PublicTimelineAPI):
    def update(self, query_params: dict = dict()) -> list[Status]:
        query_params["local"] = True
        return super().update(query_params)


class ThreadAPI(EntityAPI[Status]):
    def __init__(
        self,
        settings: AuthSettings,
        status: Status,
    ):
        self.status = status
        super().__init__(settings)

    def update(self) -> list[Status]:
        thread_context_json = self._fetch_entities(
            f"/api/v1/statuses/{self.status.id}/context"
        )
        thread_context = Context.model_validate_json(thread_context_json)

        thread = thread_context.ancestors.copy()
        thread.append(self.status)
        thread.extend(thread_context.descendants)

        self._entities = thread
        return self._entities
