import requests
from fediboat.api.account import AccountAPI
from fediboat.settings import AuthSettings


class TimelineAPI(AccountAPI):
    def __init__(
        self,
        settings: AuthSettings,
        timeline_name: str = "home",
    ):
        self.timeline_name = timeline_name
        self._timeline_data: list[dict] = list(dict())
        super().__init__(settings)

    def update(self) -> list[dict]:
        query_params = dict()
        if len(self._timeline_data) != 0:
            since_id = self._timeline_data[0]["id"]
            query_params["since_id"] = since_id

        new_timeline_data: list[dict] = requests.get(
            f"{self.settings.instance_url}/api/v1/timelines/{self.timeline_name}",
            params=query_params,
            headers=self.headers,
        ).json()
        new_timeline_data.extend(self._timeline_data)

        self._timeline_data = new_timeline_data
        return self._timeline_data
