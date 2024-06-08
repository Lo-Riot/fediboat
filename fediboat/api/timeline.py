import requests
from fediboat.api.account import AccountAPI
from fediboat.settings import AuthSettings


class TimelineAPI(AccountAPI):
    def __init__(self, settings: AuthSettings, timeline: str = "home"):
        self.timeline = timeline
        super().__init__(settings)

    def update(self) -> dict:
        return requests.get(
            f"{self.settings.instance_url}/api/v1/timelines/{self.timeline}",
            headers=self.headers,
        ).json()
