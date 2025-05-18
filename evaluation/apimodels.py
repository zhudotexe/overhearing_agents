from pydantic import BaseModel

from evaluation.models import ExperimentInfo, SuggestionLog


# POST /eval-api/login
class LoginRequest(BaseModel):
    username: str


class LoginResponse(BaseModel):
    success: bool
    username: str
    assignments: list[ExperimentInfo]


# GET /eval-api/next-annotation
class GetNextAnnotationResponse(BaseModel):
    suggestion: SuggestionLog
    context_start: float
    context_end: float
    total: int
    remaining: int
    complete: int


# GET /eval-api/{experiment_id}/transcript
class GetExperimentTranscriptResponse(BaseModel):
    transcript: str


# POST /eval-api/annotation
class PostAnnotationRequest(BaseModel):
    username: str
    experiment_id: str
    suggestion_id: str
    score: int
    labels: list[str]
    context_start: float
    context_end: float
    comment: str | None = None
    apply_to_rest: bool = False
    apply_to_all_of_npc: bool = False
    bulk_apply_duration: int = 99999


# GET /eval-api/admin/progress
class ExperimentProgress(BaseModel):
    name: str
    complete: int
    total: int


class AnnotatorProgress(BaseModel):
    username: str
    experiments: list[ExperimentProgress]


class AdminProgressResponse(BaseModel):
    progress: list[AnnotatorProgress]
