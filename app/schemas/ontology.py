"""四期本体接口的请求/响应模型。"""
from pydantic import BaseModel, ConfigDict, Field


class EntityCreate(BaseModel):
    code: str = Field(min_length=1, max_length=64)
    kind: str
    name: str | None = None
    summary: str | None = None
    attrs: dict | None = None
    status: str | None = None


class EntityUpdate(BaseModel):
    name: str | None = None
    summary: str | None = None
    attrs: dict | None = None
    status: str | None = None


class EntityView(BaseModel):
    model_config = ConfigDict(extra="allow")

    id: int
    code: str
    kind: str
    name: str
    status: str
    source: str | None = None


class EntityPage(BaseModel):
    items: list[EntityView]
    meta: dict


class RelationUpsert(BaseModel):
    src_entity_id: int
    dst_entity_id: int
    predicate: str
    weight: float | None = None
    attrs: dict | None = None
    status: str | None = None


class RelationView(BaseModel):
    model_config = ConfigDict(extra="allow")

    id: int
    predicate: str
    src_entity_id: int
    dst_entity_id: int
    status: str


class RelationPage(BaseModel):
    items: list[RelationView]
    meta: dict


class AliasUpsert(BaseModel):
    entity_id: int
    alias: str = Field(min_length=1, max_length=160)
    confidence: str | None = None
    status: str | None = None


class AliasView(BaseModel):
    model_config = ConfigDict(extra="allow")

    id: int
    entity_id: int
    alias: str
    confidence: str
    status: str


class AliasPage(BaseModel):
    items: list[AliasView]
    meta: dict


class ReviewRequest(BaseModel):
    entity_ids: list[int] = Field(min_length=1)
    action: str = "approve"


class ReviewResult(BaseModel):
    model_config = ConfigDict(extra="allow")

    updated: int
    status: str


class GraphView(BaseModel):
    model_config = ConfigDict(extra="allow")

    root: EntityView
    nodes: list[dict]
    edge_count: int
    depth: int


class ImportResult(BaseModel):
    model_config = ConfigDict(extra="allow")

    total_entity: int
    total_relation: int


class RelinkResult(BaseModel):
    model_config = ConfigDict(extra="allow")

    relinked: int


class BackfillResult(BaseModel):
    model_config = ConfigDict(extra="allow")

    inserted: int
    scanned: int
