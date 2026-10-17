"""三期智能客服接口模型。"""
from pydantic import BaseModel, ConfigDict, Field


class ConversationCreate(BaseModel):
    channel_account_id: int | None = None


class ConversationView(BaseModel):
    model_config = ConfigDict(extra="allow")

    id: int
    conversation_no: str
    status: str
    ai_paused: bool = False
    message_count: int = 0
    title: str | None = None
    last_message_at: str | None = None
    created_at: str | None = None


class ConversationPage(BaseModel):
    page: int
    page_size: int
    total: int
    items: list[ConversationView]
    meta: dict


class MessageView(BaseModel):
    model_config = ConfigDict(extra="allow")

    id: int
    seq: int
    role: str
    content: str
    status: str
    created_at: str | None = None


class MessagePage(BaseModel):
    items: list[MessageView]
    meta: dict


class IdentityRequest(BaseModel):
    order_no: str = Field(min_length=1, max_length=32)
    phone_tail: str = Field(min_length=4, max_length=4)


class HandoffView(BaseModel):
    model_config = ConfigDict(extra="allow")

    id: int
    conversation_id: int
    reason: str
    status: str
    assignee_id: int | None = None
    summary: str | None = None


class HandoffCloseRequest(BaseModel):
    summary: str = Field(min_length=1, max_length=2000)
    back_to_ai: bool = False


class AgentMessageRequest(BaseModel):
    content: str = Field(min_length=1, max_length=2000)


class StreamRequest(BaseModel):
    content: str = Field(min_length=1, max_length=2000)
    client_msg_id: str | None = Field(default=None, max_length=64)
    identity_level: str = "public"
