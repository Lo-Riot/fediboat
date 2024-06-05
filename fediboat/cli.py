import click
import webbrowser
import json

from pathlib import Path
from .api import account


@click.group()
def cli():
    pass


@cli.command()
def login():
    auth_file_path = Path("~/.config/fediboat/auth.json").expanduser()
    if auth_file_path.exists() and auth_file_path.is_file():
        auth_file_content = json.loads(auth_file_path.read_text())
        current_user = auth_file_content["current"]

        instance_url = "https://" + auth_file_content["current"].split("@")[1]
        access_token = auth_file_content["users"][current_user]["access_token"]

        try:
            account.verify_credentials(instance_url, access_token)
            click.secho("Logged in successfully!", fg="green")
        except account.APIError as e:
            click.secho(e, err=True)
        return

    instance_url = click.prompt(
        "Instance url",
        default="https://mastodon.social",
    )
    app = account.create_app(instance_url)
    webbrowser.open(
        f"{instance_url}/oauth/authorize"
        f"?client_id={app['client_id']}&scope=read+write+follow"
        f"&redirect_uri=urn:ietf:wg:oauth:2.0:oob&response_type=code"
    )

    authz_code = click.prompt("Code")
    access_token = account.auth(
        instance_url, app["client_id"], app["client_secret"], authz_code
    )
    user = account.verify_credentials(instance_url, access_token)

    instance_domain = instance_url.replace("https://", "")
    full_username = f"{user['acct']}@{instance_domain}"

    auth_file_path.parent.mkdir(parents=True, exist_ok=True)
    with open(auth_file_path, "w") as f:
        auth_file_content = {
            "current": full_username,
            "apps": {
                instance_domain: {
                    "client_id": app["client_id"],
                    "client_secret": app["client_secret"],
                },
            },
            "users": {
                full_username: {
                    "access_token": access_token,
                },
            },
        }
        f.write(json.dumps(auth_file_content))
