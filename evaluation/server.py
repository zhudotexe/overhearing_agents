"""
This file is a simple FastAPI server to manage collecting responses from annotators.
"""

import logging
from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import Response
from fastapi.staticfiles import StaticFiles

from evaluation.apimodels import (
    AdminProgressResponse,
    AnnotatorProgress,
    ExperimentProgress,
    GetExperimentTranscriptResponse,
    GetNextAnnotationResponse,
    LoginRequest,
    LoginResponse,
    PostAnnotationRequest,
)
from evaluation.models import Classification, ExperimentInfo, LabelledSuggestion
from evaluation.utils import (
    count_suggestions_by_model_and_type,
    get_all_suggestions,
    get_annotator_assignments,
    get_audio_for_span,
    get_classifications,
    get_experiment_by_id,
    get_experiment_infos,
    get_transcript_for_span,
    get_user_annotations,
    save_annotation,
    suggestions_are_same,
)
from experiments.utils import REPO_ROOT

FRONTEND_DIST = Path(__file__).parent / "frontend/dist"
SAME_SUGGESTION_TOLERANCE = 30
SAME_SUGGESTION_TOLERANCE_POSITIVE_GAMEDATA = 300
log = logging.getLogger(__name__)

# ===== API =====
app = FastAPI()

# cors middleware
# noinspection PyTypeChecker
app.add_middleware(
    CORSMiddleware, allow_origins=["*"], allow_credentials=True, allow_methods=["*"], allow_headers=["*"]
)


@app.post("/eval-api/login")
def login(data: LoginRequest) -> LoginResponse:
    # make sure the user is in config/classifications.yaml
    all_annotators = get_annotator_assignments()
    if data.username not in all_annotators:
        raise HTTPException(
            status_code=401, detail=f"{data.username} is not a registered annotator, please contact the study leads"
        )

    all_experiments = get_experiment_infos()
    assignment_ids = all_annotators[data.username]
    assignments = []
    for assignment_id in assignment_ids:
        try:
            experiment_info = next(e for e in all_experiments if e.id == assignment_id)
        except StopIteration:
            log.warning(f"Could not find assigned experiment ID for {data.username}: {assignment_id}")
            continue
        assignments.append(experiment_info)
    return LoginResponse(success=True, username=data.username, assignments=assignments)


@app.get("/eval-api/experiments")
def get_experiments() -> list[ExperimentInfo]:
    return get_experiment_infos()


@app.get("/eval-api/classifications")
def get_valid_classifications() -> list[Classification]:
    return get_classifications()


@app.get("/eval-api/next-annotation")
def get_next_incomplete_annotation(experiment_id: str, username: str) -> GetNextAnnotationResponse:
    filtered_suggestions, labelled_ids, suggestions_to_do = get_annotations_to_do(username, experiment_id)
    if not suggestions_to_do:
        raise HTTPException(status_code=400, detail="You have finished all annotations for this experiment")

    # find the right endpoint for the context - max of all same suggestions
    suggestion = suggestions_to_do[0]
    same_suggestions = list(get_same_suggestions(suggestion, suggestions_to_do, tolerance=SAME_SUGGESTION_TOLERANCE))
    end = max((s.end for s in same_suggestions), default=suggestion.end)
    return GetNextAnnotationResponse(
        suggestion=suggestion,
        context_start=suggestion.start,
        context_end=end,
        total=len(filtered_suggestions),
        remaining=len(suggestions_to_do),
        complete=len(labelled_ids),
    )


@app.get("/eval-api/{experiment_id}/transcript")
def get_experiment_transcript(experiment_id: str, start: float, end: float):
    experiment = get_experiment_by_id(experiment_id)
    transcript = get_transcript_for_span(REPO_ROOT / experiment.transcript_fp, start, end)
    return GetExperimentTranscriptResponse(transcript=transcript)


@app.get("/eval-api/{experiment_id}/audio")
def get_experiment_transcript(experiment_id: str, start: float, end: float):
    experiment = get_experiment_by_id(experiment_id)
    wav_io = get_audio_for_span(REPO_ROOT / experiment.pcm_fp, start, end)
    return Response(content=wav_io.read(), media_type="audio/wav")


@app.post("/eval-api/annotation")
def post_annotation(data: PostAnnotationRequest) -> GetNextAnnotationResponse:
    # get all the things we need (and also do some validation)
    all_suggestions = get_all_suggestions(data.experiment_id)
    suggestion = next(s for s in all_suggestions if s.suggestion_id == data.suggestion_id)
    # the label for the instance that was just annotated
    label = LabelledSuggestion(
        suggestion_id=data.suggestion_id,
        who=data.username,
        score=data.score,
        labels=data.labels,
        context_start=data.context_start,
        context_end=data.context_end,
        comment=data.comment,
        why="manual",
        entry=suggestion,
    )
    save_annotation(data.experiment_id, label)
    # if it's a bulk apply, find duplicates within the set time
    # if it's positive and a gamedata suggestion, all the same suggestions within 5 minutes are the same
    # otherwise, all the same suggestions within 30 seconds are the same
    if data.apply_to_rest or data.apply_to_all_of_npc:
        tolerance = data.bulk_apply_duration
    elif data.score > 0 and suggestion.suggestion["suggest_type"] == "gamedata":
        tolerance = SAME_SUGGESTION_TOLERANCE_POSITIVE_GAMEDATA
    else:
        tolerance = SAME_SUGGESTION_TOLERANCE
    # and apply the label to all the other ones that are the same
    filtered_suggestions, labelled_ids, suggestions_to_do = get_annotations_to_do(data.username, data.experiment_id)
    for other_suggestion in get_same_suggestions(
        suggestion,
        suggestions_to_do,
        tolerance=tolerance,
        match_npc_name_only=data.apply_to_all_of_npc,
        strict_match_improvised_npc=data.apply_to_rest,
    ):
        label2 = LabelledSuggestion(
            suggestion_id=other_suggestion.suggestion_id,
            who=data.username,
            score=data.score,
            labels=data.labels,
            context_start=data.context_start,
            context_end=data.context_end,
            comment=data.comment,
            why=f"copied from {data.suggestion_id} @ tolerance {tolerance}",
            entry=other_suggestion,
        )
        save_annotation(data.experiment_id, label2)

    # then return the next one to do
    return get_next_incomplete_annotation(data.experiment_id, data.username)


# ---- admin ----
@app.get("/eval-api/admin/progress")
def get_admin_progress():
    """Return the progress of each annotator"""
    all_annotators = get_annotator_assignments()
    out = []
    for username, assignment_ids in all_annotators.items():
        experiment_progress = []
        for experiment_id in assignment_ids:
            filtered_suggestions, labelled_ids, suggestions_to_do = get_annotations_to_do(username, experiment_id)
            experiment_progress.append(
                ExperimentProgress(name=experiment_id, complete=len(labelled_ids), total=len(filtered_suggestions))
            )
        out.append(AnnotatorProgress(username=username, experiments=experiment_progress))
    return AdminProgressResponse(progress=out)


# ---- utils ----
def get_annotations_to_do(username, experiment_id):
    previous_annotations = get_user_annotations(experiment_id, username)
    all_suggestions = get_all_suggestions(experiment_id)

    # ignore any model that suggested more than the greedy baseline
    # this usually means it got stuck in some loop, and it's not worth annotating - we'll just eval it on the set
    # of potentially valid options instead
    suggestion_counts = count_suggestions_by_model_and_type(experiment_id)
    text_span_count = suggestion_counts["text.spans"].total()
    ignored_model_ids = {
        m
        for m in suggestion_counts
        if (suggestion_counts[m].total() > text_span_count and "openai" not in m)
        # in first round of annotations these models did not produce unique positive results, filter out to avoid noise
        or (m.startswith(("qwen-25.", "phi-4.")))
    }
    filtered_suggestions = [s for s in all_suggestions if s.model_key not in ignored_model_ids]

    labelled_ids = set(l.suggestion_id for l in previous_annotations if l.entry.model_key not in ignored_model_ids)
    suggestions_to_do = [s for s in filtered_suggestions if s.suggestion_id not in labelled_ids]
    return filtered_suggestions, labelled_ids, suggestions_to_do


def get_same_suggestions(src, others, *, tolerance=30, match_npc_name_only=False, strict_match_improvised_npc=False):
    for other_suggestion in others:
        if not other_suggestion.end >= src.end:
            continue
        if not suggestions_are_same(
            src,
            other_suggestion,
            tolerance=tolerance,
            match_npc_name_only=match_npc_name_only,
            strict_match_improvised_npc=strict_match_improvised_npc,
        ):
            continue
        yield other_suggestion


# frontend static files
if not FRONTEND_DIST.exists():
    raise RuntimeError(f"The {FRONTEND_DIST} directory does not exist. You probably need to run `npm run build`.")
app.mount("/", StaticFiles(directory=FRONTEND_DIST, html=True), name="frontend")

if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="127.0.0.1", port=8000)
