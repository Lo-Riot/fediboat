from abc import abstractmethod
from pydantic import TypeAdapter
import requests

from fediboat.api.account import AccountAPI
from fediboat.settings import AuthSettings
from fediboat.entities import Context, Status


class StatusAPI(AccountAPI):
    def __init__(self, settings: AuthSettings, api_endpoint: str):
        self.api_endpoint = api_endpoint
        self._statuses: list[Status] = list()
        super().__init__(settings)

    def _fetch_statuses(self, query_params: dict | None = None) -> str:
        return requests.get(
            self.settings.instance_url + self.api_endpoint,
            params=query_params,
            headers=self.headers,
        ).text

    def get_status(self, index: int) -> Status:
        return self._statuses[index]

    @abstractmethod
    def update(self) -> list[Status]:
        """Updates statuses"""


class TimelineAPI(StatusAPI):
    def __init__(
        self,
        settings: AuthSettings,
        timeline: str = "home",
    ):
        self.timeline = timeline
        self.statuses_validator = TypeAdapter(list[Status])
        super().__init__(settings, api_endpoint=f"/api/v1/timelines/{self.timeline}")

    def update(self) -> list[Status]:
        query_params = dict()
        if len(self._statuses) != 0:
            since_id = self._statuses[0].id
            query_params["since_id"] = since_id

        new_statuses_json = self._fetch_statuses(query_params)
        new_statuses = self.statuses_validator.validate_json(new_statuses_json)
        new_statuses.extend(self._statuses)

        self._statuses = new_statuses
        return self._statuses


class ThreadAPI(StatusAPI):
    def __init__(
        self,
        settings: AuthSettings,
        status: Status,
    ):
        self.status = status
        super().__init__(settings, api_endpoint=f"/api/v1/statuses/{status.id}/context")

    def update(self) -> list[Status]:
        thread_context_json = self._fetch_statuses()
        thread_context = Context.model_validate_json(thread_context_json)

        thread = thread_context.ancestors.copy()
        thread.append(self.status)
        thread.extend(thread_context.descendants)

        self._statuses = thread
        return self._statuses
