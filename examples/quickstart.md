# 5-minute Quickstart

End-to-end mini run on a 14-sample subset (2 per language).

## 1. Install

```bash
pip install -e ".[eval]"
cp .env.example .env       # fill in at least one provider's API key
```

## 2. Inspect the dataset

```bash
python -m tools.stats
python -m tools.show --id go-method-e9ac561d7779
```

## 3. Slice a 14-row mini set (already provided as ``examples/mini.csv``)

```bash
python -m tools.slice --language python --type method -o examples/python_method.csv
```

## 4. Run the LLM judge on the mini set

```bash
python evaluations/run_delulu_judges.py \
    --data examples/mini.csv \
    --cache-dir examples/results \
    --models GPT-5.5
```

Outputs to `examples/results/GPT-5.5_cache.json` + `judge_report.json`.

## 5. Run the metrics tool on a smoke prediction file

`examples/smoke_predictions.csv` ships in this repo: 14 rows whose
``model_completion`` column is just the golden completion (so
``pass@1`` should be ≈ 1.0, ``exact_match`` should be 1.0).

```bash
python evaluations/run_completion_metrics.py \
    --predictions examples/smoke_predictions.csv \
    --model-name golden-baseline \
    --cache-dir examples/results \
    --smoke-test
```

This pulls 14 verifier images and runs `verify patch` on each, end-to-end.
Expect to wait a couple of minutes the first time while images download.

## 6. Browse the dataset visually

```bash
docker run --rm -p 8000:8000 \
    -v "$PWD/data:/app/output" \
    -v /var/run/docker.sock:/var/run/docker.sock \
    delulubench/delulu-viewer:v1
```

Open http://localhost:8000.
