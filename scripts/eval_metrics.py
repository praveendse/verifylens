"""Classification metrics for model_compare result files.

Positive class = PASS ("the image shows the article's subject").
  TP  real match, PASSED          FN  real match, FAILED   (genuine image rejected)
  TN  wrong image, FAILED         FP  wrong image, PASSED  (wrong image accepted: the costly error)

Run:  python -m scripts.eval_metrics output/model_eval/results-A.json [results-B.json ...]
Small, author-labelled sample: read the 95% intervals before comparing numbers.
"""
import json
import math
import sys
from pathlib import Path


def wilson(k: int, n: int, z: float = 1.96) -> tuple[float, float]:
    """95% Wilson score interval for a proportion k/n."""
    if n == 0:
        return (math.nan, math.nan)
    p = k / n
    d = 1 + z * z / n
    c = (p + z * z / (2 * n)) / d
    h = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / d
    return (c - h, c + h)


def metrics(rows: list[dict]) -> dict:
    ok = [r for r in rows if r.get("ok")]
    tp = sum(r["expected"] and r["predicted"] for r in ok)
    fn = sum(r["expected"] and not r["predicted"] for r in ok)
    tn = sum(not r["expected"] and not r["predicted"] for r in ok)
    fp = sum(not r["expected"] and r["predicted"] for r in ok)
    n = tp + fn + tn + fp
    div = lambda a, b: a / b if b else math.nan  # noqa: E731
    precision, recall, specificity = div(tp, tp + fp), div(tp, tp + fn), div(tn, tn + fp)
    mcc_den = math.sqrt((tp + fp) * (tp + fn) * (tn + fp) * (tn + fn))
    out = {
        "n": n, "errors": len(rows) - len(ok), "TP": tp, "FN": fn, "TN": tn, "FP": fp,
        "accuracy": div(tp + tn, n), "accuracy_ci": wilson(tp + tn, n),
        "precision": precision, "recall": recall, "specificity": specificity,
        "specificity_ci": wilson(tn, tn + fp),
        "f1": div(2 * precision * recall, precision + recall),
        "balanced_accuracy": (recall + specificity) / 2,
        "mcc": div(tp * tn - fp * fn, mcc_den),
    }
    flagged = [r for r in ok if r.get("needs_review")]
    if any("needs_review" in r for r in ok):
        wrong = [r for r in ok if r["predicted"] != r["expected"]]
        out.update(
            flagged=len(flagged),
            errors_flagged=sum(r.get("needs_review") for r in wrong), wrong=len(wrong),
            false_alarms=sum(r.get("needs_review") for r in ok if r["predicted"] == r["expected"]),
            # FP that a person reviewing flagged results would catch
            fp_unflagged=sum(not r["expected"] and r["predicted"] and not r.get("needs_review") for r in ok),
        )
    return out


def by_kind(rows: list[dict]) -> dict[str, str]:
    kinds = {}
    for r in rows:
        if r.get("ok"):
            k = kinds.setdefault(r["kind"], [0, 0])
            k[0] += r["predicted"] == r["expected"]
            k[1] += 1
    return {kind: f"{a}/{b}" for kind, (a, b) in kinds.items()}


def main(paths: list[str]) -> None:
    for path in paths:
        rows = json.loads(Path(path).read_text())["results"]
        mode = rows[0].get("mode", "standard") if rows else "?"
        m = metrics(rows)
        pct = lambda x: f"{100 * x:5.1f}%"  # noqa: E731
        print(f"\n== {Path(path).name}  ({rows[0]['model'] if rows else '?'}, mode={mode})")
        print(f"   confusion: TP={m['TP']} FN={m['FN']} TN={m['TN']} FP={m['FP']}  (n={m['n']}, failed calls={m['errors']})")
        lo, hi = m["accuracy_ci"]
        print(f"   accuracy    {pct(m['accuracy'])}  (95% CI {pct(lo)}–{pct(hi)})")
        print(f"   precision   {pct(m['precision'])}  of PASS verdicts, how many were right")
        print(f"   recall      {pct(m['recall'])}  of genuine images, how many PASSED")
        lo, hi = m["specificity_ci"]
        print(f"   specificity {pct(m['specificity'])}  of wrong images, how many FAILED (95% CI {pct(lo)}–{pct(hi)})")
        print(f"   F1 {m['f1']:.3f}   balanced accuracy {pct(m['balanced_accuracy'])}   MCC {m['mcc']:.3f}")
        print(f"   by kind: {by_kind(rows)}")
        if "flagged" in m:
            print(f"   needs review: {m['flagged']} flagged; caught {m['errors_flagged']}/{m['wrong']} errors; "
                  f"{m['false_alarms']} false alarms; wrong images accepted AND unflagged: {m['fp_unflagged']}")


if __name__ == "__main__":
    main(sys.argv[1:])
