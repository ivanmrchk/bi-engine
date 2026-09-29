#!/usr/bin/env bash
# Generate data with a given seed, run the whole pipeline into a fresh
# database of its own, and grade the result against that seed's answer key.
#
#   evaluation/evaluate_seed.sh 7
#   PYTHON=.venv/Scripts/python evaluation/evaluate_seed.sh 7    # on Windows
#
# Needs the postgres service running (docker compose up -d postgres).
set -euo pipefail

# Git Bash on Windows rewrites arguments that look like Unix paths
# (/data/... becomes C:/Program Files/Git/data/...); container paths must pass through untouched.
export MSYS_NO_PATHCONV=1

seed="${1:?usage: evaluate_seed.sh SEED}"
repository_root="$(cd "$(dirname "$0")/.." && pwd)"
python="$(cd "$repository_root" && realpath "${PYTHON:-$(command -v python)}")"
database="bi_engine_seed_${seed}"
data_dir="data/seed_${seed}"  # relative to the repository root, for docker compose

cd "$repository_root/generator"
"$python" -m synthetic_data --seed "$seed" --data-dir "../$data_dir"

cd "$repository_root"
docker compose exec -T postgres dropdb -U postgres --if-exists "$database"
docker compose exec -T postgres createdb -U postgres "$database"

run_in_api_container() {
    docker compose run --rm --no-deps \
        -e DATABASE_URL="postgresql+psycopg://postgres:postgres@postgres:5432/$database" \
        -v "./$data_dir/raw:/data/evaluation_raw:ro" \
        api "$@"
}
run_in_api_container python -m app.migrations
run_in_api_container python -m app.ingestion --raw-dir /data/evaluation_raw
run_in_api_container python -m app.clean_layer

cd "$repository_root/evaluation"
"$python" -m grading \
    --answer-key "../$data_dir/answer_key" \
    --database-url "postgresql://postgres:postgres@localhost:5434/$database"
