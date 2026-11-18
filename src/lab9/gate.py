"""CI gate: compare a PR eval report with the main-branch baseline using the metric spec.

    python -m lab9.gate --pr reports/eval_workflow.json --baseline reports/baseline_v1.json

exit 0 = merge, exit 1 = blocked. Safety metrics: max 0, no averaging away.
Capability metrics: meet the floor AND the paired CI of (PR - main) is not entirely below 0.
Thresholds may only get stricter on the same eval-set version (ratchet).
"""

from __future__ import annotations

import argparse
import json
import math
from pathlib import Path

from lab8.console import utf8_stdio
from lab9 import stats
from lab9.eval import SPEC, load_spec, per_item


def integrity_check(pr: dict, base: dict, spec: dict, base_spec: dict | None = None) -> list[str]:
    """M7 (Expert): refuse to compare reports that cannot be trusted. Return a list of problems
    (empty = trustworthy). A gate that passes a broken report is worse than no gate.
    Must catch at least:
      - any metric value in pr["metrics"] that is NaN or inf
      - len(pr["rows"]) != manifest items x len(manifest seeds)   (dropped / duplicated rows)
      - the (item_id, seed) set of PR differs from the baseline's (cherry-picked seeds/items)
      - pr["evaluator_failures"] non-empty, or a row whose value for a graded spec metric is
        None (a crashed grader silently scores as "missing" and drops out of the mean)
      - base_spec given and a threshold in spec is LOOSER than in base_spec for the same
        eval-set version (ratchet: max may not rise, min may not fall, a blocking metric may
        not become non-blocking, a metric may not disappear; the same for spec["slices"],
        including dropping no_significant_drop)
      - an item's slice tags in PR rows differ from the baseline's (relabelling an item out of a
        slice hides its regression from the slice gate)"""
    problems: list[str] = []

    # 1. Any metric value in pr["metrics"] that is NaN or inf
    for k, v in (pr.get("metrics") or {}).items():
        if isinstance(v, (int, float)):
            if math.isnan(v) or math.isinf(v):
                problems.append(f"metric {k} is NaN or inf ({v})")

    # 2. len(pr["rows"]) != manifest items x len(manifest seeds)
    manifest = pr.get("manifest") or {}
    items_count = manifest.get("items")
    seeds = manifest.get("seeds") or []
    if items_count is not None and seeds:
        expected_rows = items_count * len(seeds)
        if len(pr.get("rows") or []) != expected_rows:
            problems.append(
                f"row count {len(pr.get('rows') or [])} != expected {expected_rows} "
                f"({items_count} items x {len(seeds)} seeds)"
            )

    # 3. (item_id, seed) set of PR differs from baseline
    pr_item_seeds = {(r.get("item_id"), r.get("seed")) for r in pr.get("rows") or []}
    base_item_seeds = {(r.get("item_id"), r.get("seed")) for r in base.get("rows") or []}
    if pr_item_seeds != base_item_seeds:
        problems.append("PR (item_id, seed) set differs from baseline")

    # 4. pr["evaluator_failures"] non-empty, or a row whose value for a graded spec metric is None
    if pr.get("evaluator_failures"):
        problems.append(f"{len(pr['evaluator_failures'])} evaluator failure(s)")

    spec_metric_ids = [m["id"] for m in spec.get("metrics", [])]
    row_metric_ids = [mid for mid in spec_metric_ids if any(mid in r for r in pr.get("rows", []))]
    for r in pr.get("rows") or []:
        missing = [mid for mid in row_metric_ids if r.get(mid) is None]
        if missing:
            problems.append(f"row {r.get('item_id')}@{r.get('seed')} has None for graded metric(s): {missing}")
            break

    # 5. An item's slice tags in PR rows differ from the baseline's
    base_slices = {
        (r.get("item_id"), r.get("seed")): tuple(sorted(r.get("slices") or []))
        for r in base.get("rows") or []
    }
    for r in pr.get("rows") or []:
        key = (r.get("item_id"), r.get("seed"))
        if key in base_slices and tuple(sorted(r.get("slices") or [])) != base_slices[key]:
            problems.append(f"slice tags for {key} differ from baseline")
            break

    # 6. Ratchet: base_spec given and a threshold in spec is LOOSER than in base_spec
    if base_spec and spec.get("eval_set_version") == base_spec.get("eval_set_version"):
        base_metrics = {m["id"]: m for m in base_spec.get("metrics", [])}
        for mid, bm in base_metrics.items():
            sm = next((m for m in spec.get("metrics", []) if m["id"] == mid), None)
            if sm is None:
                problems.append(f"metric {mid} disappeared from spec (ratchet)")
                continue
            if bm.get("blocking") and not sm.get("blocking"):
                problems.append(f"metric {mid} blocking turned off (ratchet)")
            b_drop = bm.get("threshold", {}).get("no_significant_drop")
            s_drop = sm.get("threshold", {}).get("no_significant_drop")
            if b_drop and not s_drop:
                problems.append(f"metric {mid} dropped no_significant_drop (ratchet)")
            b_min = bm.get("threshold", {}).get("min")
            s_min = sm.get("threshold", {}).get("min")
            if b_min is not None and (s_min is None or s_min < b_min):
                problems.append(f"metric {mid} min threshold fell from {b_min} to {s_min} (ratchet)")
            b_max = bm.get("threshold", {}).get("max")
            s_max = sm.get("threshold", {}).get("max")
            if b_max is not None and (s_max is None or s_max > b_max):
                problems.append(f"metric {mid} max threshold rose from {b_max} to {s_max} (ratchet)")
            b_inc = bm.get("threshold", {}).get("max_increase")
            s_inc = sm.get("threshold", {}).get("max_increase")
            if b_inc is not None and (s_inc is None or s_inc > b_inc):
                problems.append(f"metric {mid} max_increase rose from {b_inc} to {s_inc} (ratchet)")

        base_slices_spec = {s["name"]: s for s in base_spec.get("slices", [])}
        spec_slices = {s["name"]: s for s in spec.get("slices", [])}
        for sname, bs_s in base_slices_spec.items():
            if sname not in spec_slices:
                problems.append(f"slice {sname} disappeared from spec (ratchet)")
                continue
            ss_s = spec_slices[sname]
            if bs_s.get("blocking") and not ss_s.get("blocking"):
                problems.append(f"slice {sname} blocking turned off (ratchet)")
            if bs_s.get("no_significant_drop") and not ss_s.get("no_significant_drop"):
                problems.append(f"slice {sname} dropped no_significant_drop (ratchet)")
            if bs_s.get("min") is not None:
                if ss_s.get("min") is None or ss_s["min"] < bs_s["min"]:
                    problems.append(f"slice {sname} min fell from {bs_s.get('min')} to {ss_s.get('min')} (ratchet)")

    return problems


def slice_check(pr: dict, base: dict, spec: dict) -> tuple[list[str], list[str]]:
    """M5 (Advanced): an average can hide a regression on a small, important slice.
    For each entry of spec["slices"] ({"name", "metric", "min"?, "no_significant_drop"?, "blocking"}):
      - value = mean of per_item(pr, metric, slice_name=name)
      - fail if below "min", or if no_significant_drop and the paired CI over the slice's items
        lies entirely below 0
    Return (blocked ids like "slice:money_movement/pass_rate", report lines)."""
    blocked: list[str] = []
    lines: list[str] = []
    bs = spec.get("bootstrap", {})

    for s in spec.get("slices", []):
        name = s["name"]
        metric = s.get("metric", "pass_rate")
        slice_id = f"slice:{name}/{metric}"
        a = per_item(pr, metric, slice_name=name)
        b = per_item(base, metric, slice_name=name)
        val = sum(a.values()) / len(a) if a else 0.0

        verdict = "ok"
        note = ""
        min_th = s.get("min")
        if min_th is not None and val < min_th:
            verdict = "fail"

        if s.get("no_significant_drop") and a and b:
            keys = sorted(set(a) & set(b))
            if keys:
                d, lo, hi = stats.paired_bootstrap(
                    [a[k] for k in keys],
                    [b[k] for k in keys],
                    n_resamples=bs.get("n_resamples", 1000),
                    rng=bs.get("rng", 2027),
                )
                note = f"Δ {d:+.3f} CI [{lo:+.3f}, {hi:+.3f}]"
                if hi < 0:
                    verdict = "fail"

        if verdict != "ok" and s.get("blocking"):
            blocked.append(slice_id)

        label = "ok" if verdict == "ok" else ("BLOCK" if s.get("blocking") else "warn")
        th_dict = {k: s[k] for k in ("min", "no_significant_drop") if k in s}
        lines.append(f"  {slice_id:<22} {val:<8.4f} {json.dumps(th_dict):<40} {note:<28} {label}")

    return blocked, lines


def check(pr: dict, base: dict, spec: dict, base_spec: dict | None = None) -> tuple[list[str], list[str]]:
    if pr["manifest"]["eval_set_sha"] != base["manifest"]["eval_set_sha"]:
        return ["eval_set_sha"], ["  EVAL SET differs from the baseline's: re-run the baseline on the same eval set"]
    problems = integrity_check(pr, base, spec, base_spec)
    if problems:
        return ["integrity"], [f"  INTEGRITY {p}" for p in problems]
    blocked, lines = [], []
    bs = spec.get("bootstrap", {})
    for m in spec["metrics"]:
        mid, th, val = m["id"], m.get("threshold", {}), pr["metrics"].get(m["id"])
        verdict, note = "ok", ""
        if val is None:
            verdict = "missing"
        elif "max" in th and val > th["max"]:
            verdict = "fail"
        elif "min" in th and val < th["min"]:
            verdict = "fail"
        elif "max_increase" in th and base["metrics"].get(mid):
            if val > base["metrics"][mid] * (1 + th["max_increase"]):
                verdict = "fail"
        if th.get("no_significant_drop") and val is not None:
            a, b = per_item(pr, mid), per_item(base, mid)
            keys = sorted(set(a) & set(b))
            d, lo, hi = stats.paired_bootstrap([a[k] for k in keys], [b[k] for k in keys],
                                               n_resamples=bs.get("n_resamples", 1000), rng=bs.get("rng", 2027))
            note = f"Δ {d:+.3f} CI [{lo:+.3f}, {hi:+.3f}]"
            if hi < 0:
                verdict = "fail"
        if verdict != "ok" and m.get("blocking"):
            blocked.append(mid)
        label = {"ok": "ok", "missing": "MISSING"}.get(verdict, "BLOCK" if m.get("blocking") else "warn")
        lines.append(f"  {mid:<22} {val!s:<8} {json.dumps(th):<40} {note:<28} {label}")
    if spec.get("slices"):
        sb, sl = slice_check(pr, base, spec)
        blocked += sb
        lines += sl
    return blocked, lines


def main(argv: list[str] | None = None) -> int:
    utf8_stdio()
    ap = argparse.ArgumentParser(prog="lab9.gate")
    ap.add_argument("--pr", required=True)
    ap.add_argument("--baseline", required=True)
    ap.add_argument("--spec", default=str(SPEC))
    ap.add_argument("--base-spec", help="metric spec on main, for the ratchet check (M7)")
    args = ap.parse_args(argv)
    pr = json.loads(Path(args.pr).read_text(encoding="utf-8"))
    base = json.loads(Path(args.baseline).read_text(encoding="utf-8"))
    base_spec = load_spec(Path(args.base_spec)) if args.base_spec else None
    blocked, lines = check(pr, base, load_spec(Path(args.spec)), base_spec)
    print(f"gate: PR {pr['run_id']} vs main {base['run_id']} · eval set {pr['manifest']['eval_set_sha']}")
    print("\n".join(lines))
    if blocked:
        print(f"exit 1 — blocked: {', '.join(blocked)}")
        return 1
    print("exit 0 — merge")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
