"""知识库接口的请求与响应模型（全部 /api/v1/knowledge/*）。"""
from pydantic import BaseModel, ConfigDict, Field


class ChunkPreviewItem(BaseModel):
    ord: int
    title_path: str = ""
    content: str
    char_count: int
    line_start: int
    line_end: int


class ChunkPreviewRequest(BaseModel):
    content_md: str = Field(min_length=1, max_length=200_000)
    first_line: int = Field(default=1, ge=1)


class ImportErrorItem(BaseModel):
    model_config = ConfigDict(extra="allow")

    file: str
    reason: str
    line: int | None = None


class ImportJobView(BaseModel):
    id: int
    source_type: str
    status: str
    total: int
    succeeded: int
    failed: int
    skipped: int
    errors: list[ImportErrorItem] = []
    created_at: str | None = None


class RuleView(BaseModel):
    model_config = ConfigDict(extra="allow")

    id: int
    rule_id: str
    source_kind: str
    condition: dict
    action: dict
    forbid: list = []
    priority: int
    status: str
    conflict_group: str | None = None
    source_file: str | None = None


class RuleCreate(BaseModel):
    rule_id: str = Field(min_length=1, max_length=48)
    source_kind: str = "manual"
    condition: dict
    action: dict = {}
    forbid: list = []
    priority: int = 100
    status: str = "DRAFT"
    conflict_group: str | None = None


class RuleUpdate(BaseModel):
    condition: dict | None = None
    action: dict | None = None
    forbid: list | None = None
    priority: int | None = None
    status: str | None = None
    conflict_group: str | None = None


class RuleImportResult(BaseModel):
    imported: int
    updated: int
    total: int
    by_source_kind: dict[str, int] = {}
    open_conflicts: int = 0


class RuleConflictView(BaseModel):
    model_config = ConfigDict(extra="allow")

    id: int
    rule_a_id: int
    rule_b_id: int
    conflict_type: str
    severity: str
    status: str
    detail: dict = {}


class VersionBase(BaseModel):
    model_config = ConfigDict(extra="allow")

    id: int
    document_pk: int
    version: int
    status: str
    checksum: str
    change_summary: str | None = None
    effective_from: str | None = None
    published_at: str | None = None


class VersionCreateRequest(BaseModel):
    content_md: str = Field(min_length=1, max_length=500_000)
    change_summary: str | None = Field(default=None, max_length=2000)


class PublishRequest(BaseModel):
    change_summary: str = Field(min_length=1, max_length=2000)
    effective_from: str | None = None


class PublishResult(VersionBase):
    publish_info: dict = {}
    reasons: list[str] = []


class ReviewTaskView(BaseModel):
    model_config = ConfigDict(extra="allow")

    id: int
    document_version_id: int
    assignee_id: int | None = None
    status: str
    decision: str | None = None
    note: str | None = None
    self_review: bool = False


class ReviewDecideRequest(BaseModel):
    decision: str
    note: str = Field(min_length=1, max_length=2000)


class ReviewCommentCreate(BaseModel):
    anchor: dict = {}
    content: str = Field(min_length=1, max_length=4000)


class ReviewCommentView(BaseModel):
    model_config = ConfigDict(extra="allow")

    id: int
    version_id: int
    task_id: int | None = None
    author_id: int | None = None
    anchor: dict = {}
    content: str
    resolved: bool = False


class RetrievalFilters(BaseModel):
    category: str | None = None
    product_scope: str | None = None
    channel_scope: list[str] | None = None


class RetrievalRequest(BaseModel):
    query: str = Field(min_length=1, max_length=2000)
    top_k: int = Field(default=10, ge=1, le=50)
    filters: RetrievalFilters = RetrievalFilters()
    identity_level: str = "public"


class RetrievalHit(BaseModel):
    model_config = ConfigDict(extra="allow")

    source_type: str = "chunk"
    chunk_id: int
    document_id: str
    document_pk: int
    version: int
    chunk_ord: int
    title_path: str = ""
    line_start: int | None = None
    line_end: int | None = None
    snippet: str = ""


class RetrievalResult(BaseModel):
    hits: list[RetrievalHit]
    debug: dict = {}


class DocumentView(BaseModel):
    model_config = ConfigDict(extra="allow")

    id: int
    document_id: str
    title: str
    category: str
    owner: str | None = None
    status: str
    current_version: int | None = None
    identity_level: str = "public"
    chunk_count: int | None = None


class PageMeta(BaseModel):
    page: int
    page_size: int
    total: int


class DocumentPage(BaseModel):
    page: int
    page_size: int
    total: int
    items: list[DocumentView]
    meta: PageMeta


class EmbeddingStats(BaseModel):
    PENDING: int = 0
    READY: int = 0
    FAILED: int = 0
