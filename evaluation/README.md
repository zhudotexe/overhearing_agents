# Evaluations

1. First, all experiments have to be done
2. Run `config/generate-experiments.py` -- this will `generate experiments.yaml`
3. Configure the annotation - set up `config/classifications.yaml` with labels and sub-labels
    1. only one top-level label can be chosen, but any number of its sublabels can
4. Configure annotators - assign annotators to experiment IDs in `config/annotator-assignments.yaml`
5. Build the frontend with `npm run build`
6. Run the human annotation -- host `server.py` (a FastAPI server) to collect labels for each model suggestion
    1. results per experiment will be saved in `annotations/<experiment-id>.jsonl`
7. Run `gold/deduplicate.ipynb` -- this calculates the inter-annotator agreement and does some cleanup for NPC speech
   tasks
8. Copy `annotations/to-dedup-*` to `gold/` and manually tiebreak any conflicting annotations -- each group requiring
   tiebreaking will be separated by 2 line breaks
9. Run `explore_posteval.ipynb` and `Win_explore_model_logs.ipynb` to generate final metrics and plots

## Human Evaluation Configuration

All config files are in `config/`. See comments at top of each file for an explanation.

## Annotation/Exploration Interface

- dev: `npm run dev` (runs frontend locally, configured @ `frontend/src/ts/constants.dev.ts`)
- build: `npm run build` (automatically builds for prod, configured @ `frontend/src/ts/constants.prod.ts`)
- server: `python server.py` (fastapi, post 8000)

Routes:

- `/` consent & login
- `/eval/:experimentId` suggestion annotation
- `/admin/:experimentId` experiment data viewer
- `/eval-api/admin/progress` progress of each annotator

## Deploying to Internet

To deploy the annotation interface to the Internet:

1. Clone this repo to some server
2. Edit `frontend/src/ts/constants.prod.ts` with the domain the eval interface will be served from
3. Run `npm run build` from the `frontend` directory - this will create the prod files in `frontend/dist`
4. Run `uvicorn evaluation.server:app` from the repo root, setting uvicorn's config as needed
5. (Recommended) set up a reverse proxy such as nginx to route requests to the HTTP server
