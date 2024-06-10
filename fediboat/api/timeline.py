from pydantic import TypeAdapter
import requests

from fediboat.api.account import AccountAPI
from fediboat.settings import AuthSettings
from fediboat.entities import Status


class TimelineAPI(AccountAPI):
    def __init__(
        self,
        settings: AuthSettings,
        timeline: str = "home",
    ):
        self.timeline = timeline
        self._statuses: list[Status] = list()
        super().__init__(settings)

    def update(self) -> list[Status]:
        query_params = dict()
        if len(self._statuses) != 0:
            since_id = self._statuses[0].id
            query_params["since_id"] = since_id

        adapter = TypeAdapter(list[Status])
        new_statuses_json = requests.get(
            f"{self.settings.instance_url}/api/v1/timelines/{self.timeline}",
            params=query_params,
            headers=self.headers,
        ).json()

        new_statuses = adapter.validate_python(new_statuses_json)
        new_statuses.extend(self._statuses)

        self._statuses = new_statuses
        return self._statuses
