from datetime import datetime
from enum import StrEnum, auto
from typing import Optional, Protocol

from pydantic import BaseModel


class EntityProtocol(Protocol):
    id: str


class TUIEntity(BaseModel):
    status: "Status | None"
    author: str
    notification_type: "NotificationTypeEnum | None" = None


class MediaAttachment(BaseModel):
    id: str
    type: str
    url: str
    preview_url: Optional[str] = None
    remote_url: Optional[str] = None
    meta: Optional[dict] = None
    description: Optional[str] = None
    blurhash: Optional[str] = None


class Application(BaseModel):
    name: str
    website: Optional[str] = None


class StatusMention(BaseModel):
    id: str
    username: str
    url: str
    acct: str


class StatusTag(BaseModel):
    name: str
    url: str


class CustomEmoji(BaseModel):
    shortcode: str
    url: str
    static_url: str
    visible_in_picker: bool
    category: Optional[str] = None


class PollOption(BaseModel):
    title: str
    votes_count: Optional[int] = None


class Poll(BaseModel):
    id: str
    expires_at: Optional[datetime]
    expired: bool
    multiple: bool
    votes_count: int
    voters_count: Optional[int] = None
    options: list[PollOption]
    emojis: list[CustomEmoji]
    voted: Optional[bool] = None
    own_votes: Optional[list[int]] = None


class PreviewCard(BaseModel):
    url: str
    title: str
    description: str
    type: str
    author_name: str
    author_url: str
    provider_name: str
    provider_url: str
    html: str
    width: int
    height: int
    image: Optional[str] = None
    embed_url: str
    blurhash: Optional[str] = None


class FilterKeyword(BaseModel):
    id: str
    keyword: str
    whole_word: bool


class FilterStatus(BaseModel):
    id: str
    status_id: str


class Filter(BaseModel):
    id: str
    title: str
    context: list[str]
    expires_at: Optional[datetime] = None
    filter_action: str
    keywords: list[FilterKeyword]
    statuses: list[FilterStatus]


class FilterResult(BaseModel):
    filter: Filter
    keyword_matches: Optional[list[str]] = None
    status_matches: Optional[list[str]] = None


class Field(BaseModel):
    name: str
    value: str
    verified_at: Optional[datetime] = None


class Account(BaseModel):
    id: str
    username: str
    acct: str
    url: str
    display_name: str
    note: str
    avatar: str
    avatar_static: str
    header: str
    header_static: str
    locked: bool
    fields: list[Field]
    emojis: list[CustomEmoji]
    bot: bool
    group: bool
    discoverable: bool | None = None
    noindex: Optional[bool] = None
    moved: Optional["Account"] = None
    suspended: Optional[bool] = None
    limited: Optional[bool] = None
    created_at: datetime
    last_status_at: Optional[datetime] = None
    statuses_count: int
    followers_count: int
    following_count: int
    source: Optional[dict] = None


class Status(BaseModel):
    id: str
    uri: str
    created_at: datetime
    account: Account
    content: str
    visibility: str
    sensitive: bool
    spoiler_text: str
    media_attachments: list[MediaAttachment]
    application: Optional[Application] = None
    mentions: list[StatusMention]
    tags: list[StatusTag]
    emojis: list[CustomEmoji]
    reblogs_count: int
    favourites_count: int
    replies_count: int
    url: Optional[str] = None
    in_reply_to_id: Optional[str] = None
    in_reply_to_account_id: Optional[str] = None
    reblog: Optional["Status"] = None
    poll: Optional[Poll] = None
    card: Optional[PreviewCard] = None
    language: Optional[str] = None
    text: Optional[str] = None
    edited_at: Optional[datetime] = None
    favourited: Optional[bool] = None
    reblogged: Optional[bool] = None
    muted: Optional[bool] = None
    bookmarked: Optional[bool] = None
    pinned: Optional[bool] = None
    filtered: Optional[list[FilterResult]] = None


class Context(BaseModel):
    ancestors: list[Status]
    descendants: list[Status]


class Report(BaseModel):
    id: str
    action_taken: bool
    action_taken_at: Optional[datetime] = None
    category: str
    comment: str
    forwarded: bool
    created_at: datetime
    status_ids: Optional[list[str]] = None
    rule_ids: Optional[list[str]] = None
    target_account: Account


class NotificationTypeEnum(StrEnum):
    reply = auto()
    favourite = auto()
    mention = auto()
    reblog = auto()
    follow = auto()
    follow_request = auto()
    moderation_warning = auto()
    severed_relationships = auto()
    status = auto()
    poll = auto()
    update = auto()
    admin_sign_up = "admin.sign_up"
    admin_report = "admin.report"


class Notification(BaseModel):
    id: str
    type: NotificationTypeEnum
    created_at: datetime
    account: Account
    status: Optional[Status] = None
    report: Optional[Report] = None
