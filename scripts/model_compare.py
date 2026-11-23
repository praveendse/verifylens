"""Compare Gemini models on the image-relevance decision.

Labelled cases (article text + image):
  match     - the article with its own Wikipedia infobox image   -> expect True
  obvious   - the article with an unrelated article's image      -> expect False
  near-miss - the article with a similar-looking subject's image -> expect False
              (e.g. Albert Einstein + Isaac Newton, BMW + Mercedes-Benz)

Phase 1 scrapes every article and image ONCE into output/model_eval/cache, so
every model sees identical inputs. Phase 2 calls the app's real verify_image
(same prompt, schema and validation as production) for every model x case.

Assumption: an article's own infobox image is relevant to it. That holds for
these hand-picked topics but is a label choice, not ground truth from a human
review of each image.

Run:  python -m scripts.model_compare
      python -m scripts.model_compare --models gemini-3.5-flash-lite:low
Costs real Gemini API calls (about 40 per model).
"""
import argparse
import json
import statistics
import sys
import threading
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from types import SimpleNamespace

from playwright.sync_api import sync_playwright

from google.genai import types as genai_types

from app.services import gemini_service
from app.services.gemini_service import verify_image
from app.services.wikipedia_service import download_infobox_image, scrape_article
from app.settings import Settings

OUT = Path("output/model_eval")
CALL_TIMEOUT_MS = 90_000
CACHE = OUT / "cache"

DEFAULT_MODELS = [
    "gemini-2.5-flash",          # current production default (retires 2026-12-01)
    "gemini-3.5-flash-lite:low",  # new default
    "gemini-3.5-flash-lite:minimal",
    "gemini-3.8-flash:low",
]

MATCH_TOPICS = [
    "Albert Einstein", "Marie Curie", "Eiffel Tower", "Taj Mahal", "Mount Everest",
    "BMW", "Toyota", "Sri Lanka", "Giraffe", "Bald eagle", "Sydney Opera House",
    "Mona Lisa", "Golden Gate Bridge", "Leonardo da Vinci", "Great Wall of China",
    "Western honey bee", "Tiger", "Colosseum", "Big Ben", "Apollo 11",
]
NEAR_MISS = [  # (article, image taken from)
    ("Albert Einstein", "Isaac Newton"), ("BMW", "Mercedes-Benz"), ("Tiger", "Lion"),
    ("Eiffel Tower", "Tokyo Tower"), ("Taj Mahal", "Humayun's tomb"),
    ("Golden Gate Bridge", "San Francisco–Oakland Bay Bridge"), ("Marie Curie", "Pierre Curie"),
    ("Toyota", "Honda"), ("Western honey bee", "Vespula germanica"), ("Bald eagle", "Golden eagle"),
]
OBVIOUS = [
    ("Albert Einstein", "Giraffe"), ("Taj Mahal", "BMW"), ("Mount Everest", "Mona Lisa"),
    ("Sri Lanka", "Apollo 11"), ("Sydney Opera House", "Tiger"), ("Marie Curie", "Big Ben"),
    ("Great Wall of China", "Western honey bee"), ("Colosseum", "Toyota"),
    ("Leonardo da Vinci", "Golden Gate Bridge"), ("Giraffe", "Eiffel Tower"),
]


def slug(topic):
    return "".join(c if c.isalnum() else "_" for c in topic).strip("_").lower()


def fetch_all(topics):
    """Scrape article + image for each topic, skipping ones already cached."""
    articles, failed = {}, {}
    todo = [t for t in topics if not (CACHE / slug(t) / "article.json").exists()]
    if todo:
        print(f"Fetching {len(todo)} Wikipedia articles…")
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)
            try:
                page = browser.new_page()
                for topic in todo:
                    folder = CACHE / slug(topic)
                    try:
                        article = scrape_article(page, topic)
                        image = download_infobox_image(page, article["image_url"], folder)
                        article["image_file"] = image.name
                        (folder / "article.json").write_text(json.dumps(article, indent=2))
                        print(f"  ok   {topic} -> {article['title']}")
                    except Exception as exc:  # noqa: BLE001 - record and continue
                        failed[topic] = f"{type(exc).__name__}: {exc}"
                        print(f"  FAIL {topic}: {failed[topic]}")
            finally:
                browser.close()
    for topic in topics:
        path = CACHE / slug(topic) / "article.json"
        if path.exists():
            articles[topic] = json.loads(path.read_text())
    return articles, failed


def build_cases(articles):
    cases = []
    for t in MATCH_TOPICS:
        if t in articles:
            cases.append({"kind": "match", "article": t, "image": t, "expected": True})
    for kind, pairs in (("near-miss", NEAR_MISS), ("obvious", OBVIOUS)):
        for a, i in pairs:
            if a in articles and i in articles:
                cases.append({"kind": kind, "article": a, "image": i, "expected": False})
    return cases


_REAL_CLIENT = gemini_service.genai.Client
_local = threading.local()


class _RecordingModels:
    """Passes calls through and keeps each call's raw JSON text and token usage
    for the current thread (verify_image itself only returns the parsed answer)."""

    def __init__(self, inner):
        self.inner = inner

    def generate_content(self, **kw):
        resp = self.inner.generate_content(**kw)
        usage = getattr(resp, "usage_metadata", None)
        _local.raw.append({
            "text": getattr(resp, "text", None),
            "prompt_tokens": getattr(usage, "prompt_token_count", None),
            "output_tokens": getattr(usage, "candidates_token_count", None),
            "thinking_tokens": getattr(usage, "thoughts_token_count", None),
        })
        return resp


def _recording_client(api_key):
    # verify_image only uses client.models.generate_content; keep the real
    # client referenced so it isn't closed while the call runs.
    # Hard per-request limit: without it a stalled call waits forever (an
    # earlier run hung for hours). Transient timeouts are retried in run_case.
    client = _REAL_CLIENT(api_key=api_key, http_options=genai_types.HttpOptions(timeout=CALL_TIMEOUT_MS))
    return SimpleNamespace(models=_RecordingModels(client.models), _client=client)


def run_case(case, articles, model, level, api_key):
    article = articles[case["article"]]
    image_meta = articles[case["image"]]
    image_path = CACHE / slug(case["image"]) / image_meta["image_file"]
    raw = _local.raw = []
    start = time.perf_counter()
    result = {"model": f"{model}:{level}" if level else model, **case}
    for attempt in range(4):  # back off on rate limits / transient server errors
        raw.clear()
        try:
            answer = verify_image(article, image_path, api_key=api_key, model=model,
                                  **({"thinking_level": level} if level else {}))
            result.update(ok=True, predicted=answer["matches"], reason=answer["reason"],
                          description=answer["description"])
            break
        except Exception as exc:  # noqa: BLE001
            msg = f"{type(exc).__name__}: {exc}"[:300]
            transient = any(s in msg for s in ("429", "RESOURCE_EXHAUSTED", "503", "500", "UNAVAILABLE",
                                               "Timeout", "timed out", "ReadTimeout", "ConnectTimeout"))
            if transient and attempt < 3:
                time.sleep(5 * 2 ** attempt)
                continue
            result.update(ok=False, error=msg)
            break
    result["seconds"] = round(time.perf_counter() - start, 2)
    last = raw[-1] if raw else {}
    result.update({k: last.get(k) for k in ("prompt_tokens", "output_tokens", "thinking_tokens")})
    result["attempts"] = len(raw)
    text = last.get("text") or ""
    # Did the model write "reason" before "matches" (reason-first ordering)?
    result["reason_first"] = (text.find('"reason"') < text.find('"matches"')) if '"reason"' in text and '"matches"' in text else None
    return result


def summarise(results, model):
    rows = [r for r in results if r["model"] == model]
    ok = [r for r in rows if r["ok"]]
    correct = [r for r in ok if r["predicted"] == r["expected"]]

    def acc(kind):
        k = [r for r in ok if r["kind"] == kind]
        return f"{sum(r['predicted'] == r['expected'] for r in k)}/{len(k)}" if k else "-"

    def med(key):
        vals = [r[key] for r in ok if r.get(key) is not None]
        return statistics.median(vals) if vals else None

    order = [r["reason_first"] for r in ok if r["reason_first"] is not None]
    return {
        "model": model, "cases": len(rows), "errors": len(rows) - len(ok),
        "accuracy": f"{len(correct)}/{len(ok)}" if ok else "-",
        "accuracy_pct": round(100 * len(correct) / len(ok), 1) if ok else None,
        "match": acc("match"), "near_miss": acc("near-miss"), "obvious": acc("obvious"),
        "median_s": med("seconds"), "median_prompt_tokens": med("prompt_tokens"),
        "median_output_tokens": med("output_tokens"), "median_thinking_tokens": med("thinking_tokens"),
        "reason_first": f"{sum(order)}/{len(order)}" if order else "-",
    }


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--models", nargs="+", default=DEFAULT_MODELS, help="model or model:thinking_level")
    ap.add_argument("--workers", type=int, default=4)
    args = ap.parse_args()

    api_key = Settings().gemini_api_key
    if not api_key:
        sys.exit("GEMINI_API_KEY is not set (.env or environment).")

    topics = sorted({t for t in MATCH_TOPICS} | {x for pair in NEAR_MISS + OBVIOUS for x in pair})
    articles, failed = fetch_all(topics)
    cases = build_cases(articles)
    print(f"{len(cases)} cases ({sum(c['kind'] == 'match' for c in cases)} match, "
          f"{sum(c['kind'] == 'near-miss' for c in cases)} near-miss, {sum(c['kind'] == 'obvious' for c in cases)} obvious)"
          + (f"; skipped topics: {', '.join(failed)}" if failed else ""))

    gemini_service.genai.Client = _recording_client  # installed once; per-thread sinks
    OUT.mkdir(parents=True, exist_ok=True)
    stamp = time.strftime("%Y%m%d-%H%M%S")
    # Every result is appended here as soon as it arrives, so an interrupted
    # run still leaves usable data.
    live = OUT / f"results-{stamp}.jsonl"
    lock = threading.Lock()
    results = []

    def one(case, model, level):
        r = run_case(case, articles, model, level, api_key)
        with lock:
            results.append(r)
            with live.open("a") as fh:
                fh.write(json.dumps(r) + "\n")
            mark = "ok " if r["ok"] and r["predicted"] == r["expected"] else ("ERR" if not r["ok"] else "MIS")
            print(f"   [{mark}] {r['model']:<30} {r['kind']:<9} {r['article']} + {r['image']} ({r['seconds']}s)", flush=True)
        return r

    for spec in args.models:
        model, _, level = spec.partition(":")
        print(f"\n== {spec}: {len(cases)} calls…", flush=True)
        t0 = time.perf_counter()
        with ThreadPoolExecutor(args.workers) as pool:
            batch = list(pool.map(lambda c: one(c, model, level or None), cases))
        bad = [r for r in batch if not r["ok"]]
        print(f"   done in {time.perf_counter() - t0:.0f}s, {len(bad)} errors"
              + (f" (first: {bad[0]['error']})" if bad else ""), flush=True)

    results.sort(key=lambda r: (args.models.index(r["model"]) if r["model"] in args.models else 99))
    summary = [summarise(results, spec) for spec in args.models]
    (OUT / f"results-{stamp}.json").write_text(json.dumps({"summary": summary, "results": results,
                                                            "fetch_failures": failed}, indent=2))

    print(f"\n{'model':<32}{'accuracy':>10}{'match':>8}{'near':>7}{'obvious':>9}{'errors':>8}"
          f"{'med s':>7}{'think tok':>10}{'out tok':>9}{'reason1st':>11}")
    for s in summary:
        print(f"{s['model']:<32}{s['accuracy']:>10}{s['match']:>8}{s['near_miss']:>7}{s['obvious']:>9}"
              f"{s['errors']:>8}{s['median_s'] or 0:>7.1f}{s['median_thinking_tokens'] or 0:>10.0f}"
              f"{s['median_output_tokens'] or 0:>9.0f}{s['reason_first']:>11}")

    print("\nDisagreements with the expected label:")
    for r in results:
        if r["ok"] and r["predicted"] != r["expected"]:
            print(f"  [{r['model']}] {r['kind']}: article '{r['article']}' + image of '{r['image']}' "
                  f"-> {r['predicted']} | {r['reason'][:140]}")
    print(f"\nFull results: {OUT / f'results-{stamp}.json'}")


if __name__ == "__main__":
    main()
