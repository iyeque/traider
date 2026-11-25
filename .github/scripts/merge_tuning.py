#!/usr/bin/env python3
"""Merge per-symbol tuning artifacts, enforce promotion guardrails, report.

Usage: python3 .github/scripts/merge_tuning.py <artifacts_dir> <out_json> <pr_body_md>
Writes GITHUB_OUTPUT promote=true|false and appends to GITHUB_STEP_SUMMARY.
"""
import datetime
import glob
import json
import os
import sys

artifacts, out_path, pr_body = sys.argv[1:4]
files = sorted(glob.glob(os.path.join(artifacts, "**", "tune_*.json"), recursive=True))
if not files:
    raise SystemExit("no tune_*.json artifacts found")

merged = {
    "generated_at": datetime.datetime.now(datetime.timezone.utc).isoformat(),
    "source": "Phase 1b GitHub Action: Optuna train/OOS, guarded promotion",
    "symbols": {},
}
for f in files:
    with open(f, encoding="utf-8") as fh:
        merged["symbols"].update(json.load(fh)["symbols"])

rows = []
eligible = len(merged["symbols"]) == 4
for symbol, e in sorted(merged["symbols"].items()):
    oos = e.get("oos")
    promo = e.get("promotion") or {}
    ok = bool(promo.get("eligible"))
    eligible = eligible and ok
    m = (oos or e)["metrics"]
    rows.append("| {} | ${:.2f} | ${:.2f} | {} | {:.0f}% | {} | {:.1f}% | {} |".format(
        symbol, e["train"]["final_balance"], (oos or e)["final_balance"],
        (oos or e)["trades"], float(m.get("win_rate", 0)) * 100,
        m.get("profit_factor", "?"), float(m.get("max_drawdown", 0)),
        "PROMOTE" if ok else "NO: " + "; ".join(promo.get("reasons", ["no data"])),
    ))

summary = [
    "# Traider tuning report",
    "",
    "Optuna trained on the earlier slice; figures below are the held-out out-of-sample slice.",
    "",
    "| Symbol | Train final | OOS final | OOS trades | Win rate | Profit factor | Max DD | Decision |",
    "| --- | --- | --- | --- | --- | --- | --- | --- |",
] + rows + [
    "",
    "Overall: **{}**".format("PROMOTED" if eligible else "NO PROMOTION - existing params kept"),
    "",
]
report = "\n".join(summary)
with open(pr_body, "w", encoding="utf-8") as fh:
    fh.write(report + "\n\nMerging this PR deploys the promoted parameters on the next `npm run deploy`.\n")
if os.environ.get("GITHUB_STEP_SUMMARY"):
    with open(os.environ["GITHUB_STEP_SUMMARY"], "a", encoding="utf-8") as fh:
        fh.write(report + "\n")
if os.environ.get("GITHUB_OUTPUT"):
    with open(os.environ["GITHUB_OUTPUT"], "a", encoding="utf-8") as fh:
        fh.write("promote=" + ("true" if eligible else "false") + "\n")

if eligible:
    os.makedirs(os.path.dirname(os.path.abspath(out_path)), exist_ok=True)
    with open(out_path, "w", encoding="utf-8") as fh:
        json.dump(merged, fh, indent=2)
    print("PROMOTE: wrote", out_path)
else:
    print("NO PROMOTION: guardrails failed; existing tuned_params.json left untouched")
print(report)
