from pydantic import BaseModel


class ExperimentInfo(BaseModel):
    id: str
    name: str
    log_dir: str
    pcm_fp: str
    transcript_fp: str


class Classification(BaseModel):
    key: str
    label: str
    score: int | None = None
    sublabels: list["Classification"] | None = None
    examples: list[str] | None = None
    mutex: list[str] | None = None


class SuggestionLog(BaseModel):
    start: float
    end: float
    transcript: str | None = None
    audio_fp: str | None = None
    suggestion: dict
    model_key: str
    experiment_info: ExperimentInfo

    @property
    def suggestion_id(self):
        return self.suggestion["id"]


class LabelledSuggestion(BaseModel):
    suggestion_id: str
    who: str
    score: int
    labels: list[str]
    context_start: float  # the start and end ts of the context the annotator used
    context_end: float
    comment: str | None = None
    why: str  # manual or identical to another suggestion id
    entry: SuggestionLog  # technically this is redundant but it's a pain to xref backwards so just copy it
