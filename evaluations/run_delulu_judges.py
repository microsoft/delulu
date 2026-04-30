"""
Run LLM-as-judge evaluation on the Delulu hallucination benchmark.

For each sample, two judge calls are made (golden + hallucinated completion).
A judge is "correct" on a sample when it scores the golden completion 1 AND
the hallucinated completion 0 (``both_correct``).

Per-(model, sample) results are cached as JSON so runs are resumable.

Configuration is via environment variables (see ``.env.example``):

    AZURE_OPENAI_ENDPOINT, AZURE_OPENAI_API_KEY, AZURE_OPENAI_API_VERSION,
    AZURE_OPENAI_RESPONSES_API_VERSION
    ANTHROPIC_API_KEY
    GOOGLE_API_KEY

Usage
-----
    python run_delulu_judges.py \\
        --data ../data/delulu.csv \\
        --cache-dir results/judges \\
        --models GPT-5.5 Claude-4.5-Sonnet
"""
from __future__ import annotations

import argparse
import csv
import json
import os
import re
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from typing import Optional

import requests as http_requests
from dotenv import load_dotenv
from tqdm import tqdm

try:
    from openai import AzureOpenAI
    AZURE_AVAILABLE = True
except ImportError:
    AZURE_AVAILABLE = False

try:
    from anthropic import Anthropic
    ANTHROPIC_AVAILABLE = True
except ImportError:
    ANTHROPIC_AVAILABLE = False

try:
    import google.generativeai as genai
    GEMINI_AVAILABLE = True
except ImportError:
    GEMINI_AVAILABLE = False


# ── Default model registry ──────────────────────────────────────────
# Users override `deployment` to match their own deployment names / model ids.
DEFAULT_MODELS: dict[str, dict] = {
    # Azure OpenAI (chat completions)
    "GPT-5.1":       {"deployment": "gpt-5.1",       "api": "chat",      "temperature": 1.0},
    "GPT-5.2":       {"deployment": "gpt-5.2",       "api": "chat",      "temperature": 1.0},
    "GPT-5.4":       {"deployment": "gpt-5.4",       "api": "chat",      "temperature": 1.0},
    "GPT-5.5":       {"deployment": "gpt-5.5",       "api": "chat",      "temperature": 1.0},
    # Azure OpenAI (responses API)
    "GPT-5.2-Codex": {"deployment": "gpt-5.2-codex", "api": "responses", "temperature": 1.0},
    "GPT-5.3-Codex": {"deployment": "gpt-5.3-codex", "api": "responses", "temperature": 1.0},
    # Anthropic
    "Claude-4.5-Sonnet": {"deployment": "claude-sonnet-4-5", "api": "claude", "temperature": 1.0},
    "Claude-4.5-Haiku":  {"deployment": "claude-haiku-4-5",  "api": "claude", "temperature": 1.0},
    "Claude-4.5-Opus":   {"deployment": "claude-opus-4-5",   "api": "claude", "temperature": 1.0},
    # Google
    "Gemini-2.5-Pro":   {"deployment": "gemini-2.5-pro",   "api": "gemini", "temperature": 1.0},
    "Gemini-2.5-Flash": {"deployment": "gemini-2.5-flash", "api": "gemini", "temperature": 1.0},
}

MAX_TOKENS = 4096
WORKERS_PER_MODEL = 10
SAVE_EVERY = 25

JUDGE_SYSTEM = """
You are a top-tier software engineer with deep expertise in software development and code review. Evaluate a candidate code completion that should connect the provided prefix and suffix inside the same file.

Score 1 ONLY when all of the following are true:
    - The completion keeps the file syntactically valid when placed between the prefix and suffix.
    - The completion is logically consistent with the surrounding context (same language, reasonable variable/function usage, no contradictions).
    - The completion is relevant: it advances the apparent task from the prefix toward the suffix instead of introducing unrelated or redundant code.
    - The completion does not hallucinate APIs, data, or behavior that conflict with the given context.
Otherwise score 0.

Format your response exactly as:
Detailed Reasoning: <reasoning text>
Final Average Score for Completion: <0 or 1>
""".strip()


# ── Prompt + score parsing ──────────────────────────────────────────

def build_user_prompt(prefix: str, completion: str, suffix: str) -> str:
    return (
        "# Inputs #\n\n"
        f"<prefix_start>{prefix}</prefix_start>\n\n"
        f"<suffix_start>{suffix}</suffix_start>\n\n"
        f"<model_completion_start>{completion}</model_completion_end>\n\n"
        "# Outputs #\nYour analysis starts>"
    )


def parse_score(text: str) -> int:
    m = re.search(r"Final Average Score for Completion:\s*(\d+)", text)
    if m:
        return int(m.group(1))
    m = re.search(r"\bScore\b[:\s]+(\d)\b", text)
    if m:
        return int(m.group(1))
    digits = re.findall(r"\b([01])\b", text)
    if digits:
        return int(digits[-1])
    return -1


# ── Judge call dispatch ─────────────────────────────────────────────

def _call_chat(client, deployment, system, user, temperature) -> str:
    resp = client.chat.completions.create(
        model=deployment,
        messages=[
            {"role": "system", "content": system},
            {"role": "user", "content": user},
        ],
        temperature=temperature,
        max_completion_tokens=MAX_TOKENS,
    )
    return resp.choices[0].message.content or ""


def _call_responses(endpoint, api_key, api_version, deployment, system, user, temperature) -> str:
    url = f"{endpoint.rstrip('/')}/openai/responses?api-version={api_version}"
    payload = {
        "model": deployment,
        "instructions": system,
        "input": user,
        "max_output_tokens": MAX_TOKENS,
        "temperature": temperature,
    }
    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {api_key}",
    }
    r = http_requests.post(url, json=payload, headers=headers, timeout=120)
    r.raise_for_status()
    rjson = r.json()
    text = ""
    for item in rjson.get("output", []):
        if item.get("type") == "message":
            for content in item.get("content", []):
                if content.get("type") == "output_text":
                    text += content.get("text", "")
    return text or json.dumps(rjson.get("output", ""))


def _call_claude(api_key, deployment, system, user, temperature) -> str:
    client = Anthropic(api_key=api_key)
    resp = client.messages.create(
        model=deployment,
        system=system,
        messages=[{"role": "user", "content": user}],
        max_tokens=MAX_TOKENS,
        temperature=temperature,
    )
    return resp.content[0].text if resp.content else ""


def _call_gemini(api_key, deployment, system, user, temperature) -> str:
    genai.configure(api_key=api_key)
    model = genai.GenerativeModel(model_name=deployment, system_instruction=system)
    resp = model.generate_content(
        user,
        generation_config=genai.types.GenerationConfig(
            max_output_tokens=MAX_TOKENS,
            temperature=temperature,
        ),
    )
    return resp.text if resp.text else ""


def judge_one(env, client, model_cfg, prefix, completion, suffix) -> dict:
    """Run one judge call with retries. Returns {score, reasoning}."""
    deployment = model_cfg["deployment"]
    api = model_cfg["api"]
    temperature = model_cfg.get("temperature", 0.0)
    user = build_user_prompt(prefix, completion, suffix)

    for attempt in range(3):
        try:
            if api == "chat":
                text = _call_chat(client, deployment, JUDGE_SYSTEM, user, temperature)
            elif api == "responses":
                text = _call_responses(
                    env["azure_endpoint"], env["azure_key"], env["responses_api_version"],
                    deployment, JUDGE_SYSTEM, user, temperature,
                )
            elif api == "claude":
                text = _call_claude(env["anthropic_key"], deployment, JUDGE_SYSTEM, user, temperature)
            elif api == "gemini":
                text = _call_gemini(env["gemini_key"], deployment, JUDGE_SYSTEM, user, temperature)
            else:
                raise ValueError(f"Unknown api: {api}")
            return {"score": parse_score(text), "reasoning": text[:500]}
        except Exception as e:
            if attempt < 2:
                time.sleep(2 ** (attempt + 1))
            else:
                return {"score": None, "reasoning": str(e)[:200]}


# ── Sample loading & caching ────────────────────────────────────────

def load_samples(csv_path: Path) -> list[dict]:
    samples = []
    with open(csv_path, "r", encoding="utf-8") as f:
        for row in csv.DictReader(f):
            if not row.get("golden_completion"):
                continue
            samples.append({
                "benchmark_id": row["benchmark_id"],
                "language": row["language"],
                "hallucination_type": row["hallucination_type"],
                "prefix": row.get("prompt", ""),
                "suffix": row.get("suffix", ""),
                "golden": row["golden_completion"],
                "hallucinated": row["hallucinated_completion"],
            })
    return samples


def cache_path(cache_dir: Path, model_name: str) -> Path:
    safe = model_name.replace("/", "_").replace(" ", "_")
    return cache_dir / f"{safe}_cache.json"


def load_cache(cache_dir: Path, model_name: str) -> dict:
    p = cache_path(cache_dir, model_name)
    if p.exists():
        with open(p, "r") as f:
            return json.load(f)
    return {}


def save_cache(cache_dir: Path, model_name: str, cache: dict) -> None:
    with open(cache_path(cache_dir, model_name), "w") as f:
        json.dump(cache, f, indent=2)


# ── Per-model evaluation ────────────────────────────────────────────

def _api_available(api: str, env: dict) -> Optional[str]:
    """Return None if available, else a reason string."""
    if api in ("chat", "responses"):
        if not AZURE_AVAILABLE:
            return "openai package not installed"
        if not env["azure_key"] or not env["azure_endpoint"]:
            return "AZURE_OPENAI_API_KEY/ENDPOINT not set"
    elif api == "claude":
        if not ANTHROPIC_AVAILABLE:
            return "anthropic package not installed"
        if not env["anthropic_key"]:
            return "ANTHROPIC_API_KEY not set"
    elif api == "gemini":
        if not GEMINI_AVAILABLE:
            return "google-generativeai package not installed"
        if not env["gemini_key"]:
            return "GOOGLE_API_KEY not set"
    return None


def evaluate_model(model_name: str, model_cfg: dict, samples: list,
                   env: dict, cache_dir: Path) -> dict:
    api = model_cfg["api"]
    reason = _api_available(api, env)
    if reason:
        print(f"  SKIP {model_name}: {reason}")
        return load_cache(cache_dir, model_name)

    client = None
    if api in ("chat", "responses"):
        client = AzureOpenAI(
            api_key=env["azure_key"],
            azure_endpoint=env["azure_endpoint"],
            api_version=env["azure_api_version"],
        )

    cache = load_cache(cache_dir, model_name)
    remaining = [s for s in samples if s["benchmark_id"] not in cache]
    print(f"  {model_name}: cached={len(cache)} remaining={len(remaining)}")
    if not remaining:
        return cache

    pbar = tqdm(remaining, desc=model_name, unit="sample")
    for i, sample in enumerate(pbar):
        golden = judge_one(env, client, model_cfg, sample["prefix"], sample["golden"], sample["suffix"])
        halluc = judge_one(env, client, model_cfg, sample["prefix"], sample["hallucinated"], sample["suffix"])
        cache[sample["benchmark_id"]] = {
            "benchmark_id": sample["benchmark_id"],
            "language": sample["language"],
            "hallucination_type": sample["hallucination_type"],
            "golden_score": golden["score"],
            "hallucinated_score": halluc["score"],
            "golden_correct": golden["score"] == 1,
            "hallucinated_correct": halluc["score"] == 0,
            "both_correct": golden["score"] == 1 and halluc["score"] == 0,
            "golden_reasoning": golden.get("reasoning", ""),
            "hallucinated_reasoning": halluc.get("reasoning", ""),
        }
        bc = sum(1 for v in cache.values() if v.get("both_correct")) / len(cache)
        pbar.set_postfix(both_correct=f"{bc:.1%}")
        if (i + 1) % SAVE_EVERY == 0:
            save_cache(cache_dir, model_name, cache)

    save_cache(cache_dir, model_name, cache)
    return cache


# ── Reporting ───────────────────────────────────────────────────────

def summarize(all_caches: dict, cache_dir: Path) -> None:
    import pandas as pd
    rows = []
    for model_name, cache in all_caches.items():
        for r in cache.values():
            rows.append({
                "model": model_name,
                "language": r.get("language", "?"),
                "hallucination_type": r.get("hallucination_type", "?"),
                "both_correct": r.get("both_correct", False),
                "golden_correct": r.get("golden_correct", False),
                "hallucinated_correct": r.get("hallucinated_correct", False),
            })
    if not rows:
        print("No results.")
        return
    df = pd.DataFrame(rows)

    print("\nOverall:")
    overall = df.groupby("model").agg(
        N=("both_correct", "count"),
        both_correct=("both_correct", "mean"),
        golden_acc=("golden_correct", "mean"),
        halluc_acc=("hallucinated_correct", "mean"),
    ).round(4)
    print(overall.to_string())

    by_type = df.groupby(["model", "hallucination_type"]).agg(
        N=("both_correct", "count"),
        both_correct=("both_correct", "mean"),
    ).round(4)
    by_lang = df.groupby(["model", "language"]).agg(
        N=("both_correct", "count"),
        both_correct=("both_correct", "mean"),
    ).round(4)

    report = {
        "overall": overall.reset_index().to_dict(orient="records"),
        "by_type": by_type.reset_index().to_dict(orient="records"),
        "by_language": by_lang.reset_index().to_dict(orient="records"),
    }
    out = cache_dir / "judge_report.json"
    with open(out, "w") as f:
        json.dump(report, f, indent=2)
    print(f"\nReport saved: {out}")


# ── CLI ─────────────────────────────────────────────────────────────

def _load_env() -> dict:
    load_dotenv()
    return {
        "azure_endpoint": os.getenv("AZURE_OPENAI_ENDPOINT", ""),
        "azure_key": os.getenv("AZURE_OPENAI_API_KEY", ""),
        "azure_api_version": os.getenv("AZURE_OPENAI_API_VERSION", "2024-12-01-preview"),
        "responses_api_version": os.getenv("AZURE_OPENAI_RESPONSES_API_VERSION", "2025-04-01-preview"),
        "anthropic_key": os.getenv("ANTHROPIC_API_KEY", ""),
        "gemini_key": os.getenv("GOOGLE_API_KEY", ""),
    }


def main():
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--data", type=Path, default=Path(__file__).resolve().parent.parent / "data" / "delulu.csv",
                   help="Path to delulu.csv (default: ../data/delulu.csv)")
    p.add_argument("--cache-dir", type=Path, default=Path("results"),
                   help="Directory for per-model cache files (default: results/)")
    p.add_argument("--models", nargs="+", default=list(DEFAULT_MODELS.keys()),
                   help="Subset of model display-names to evaluate")
    p.add_argument("--limit", type=int, default=None, help="Limit samples (debug)")
    args = p.parse_args()

    env = _load_env()
    args.cache_dir.mkdir(parents=True, exist_ok=True)

    samples = load_samples(args.data)
    if args.limit:
        samples = samples[:args.limit]
    print(f"Loaded {len(samples)} samples from {args.data}")

    selected = {name: DEFAULT_MODELS[name] for name in args.models if name in DEFAULT_MODELS}
    unknown = [n for n in args.models if n not in DEFAULT_MODELS]
    if unknown:
        print(f"Warning: unknown models ignored: {unknown}")
    print(f"Running {len(selected)} models in parallel: {list(selected)}")

    all_caches: dict = {}
    with ThreadPoolExecutor(max_workers=max(1, len(selected))) as ex:
        futures = {ex.submit(evaluate_model, n, c, samples, env, args.cache_dir): n
                   for n, c in selected.items()}
        for fut in as_completed(futures):
            name = futures[fut]
            try:
                all_caches[name] = fut.result()
                print(f"  [done] {name}: {len(all_caches[name])} entries")
            except Exception as e:
                print(f"  [fail] {name}: {e}")
                all_caches[name] = load_cache(args.cache_dir, name)

    summarize(all_caches, args.cache_dir)


if __name__ == "__main__":
    main()
