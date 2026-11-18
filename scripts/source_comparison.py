"""Publish aggregate checks from the full-source verification beside the recorded import."""

import argparse
import html
import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SNAPSHOT = ROOT / "site/assets/source-comparison.json"
CLIMATE = "climate change within 5% of ADEME for at least 99% of products"
CHECKS = ("the build read the full export", CLIMATE)
PARITY_LINE = re.compile(r"  parity check: PASS \(\d+ scores, max rel error [0-9.eE+\-]+\)")


def read(path):
    return json.loads(path.read_text(encoding="utf-8"))


def collect(report, log, brightway_log):
    """Copy only public totals, identifiers and verbatim allowlisted check lines."""
    data = read(report)
    if data["csv_source"]["variant"] != "full" or set(data["checks"]) != set(CHECKS):
        raise ValueError("Expected the full input, its source check and climate check")
    if not re.fullmatch(r"\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2} (?:CET|CEST|UTC)", data["started"]):
        raise ValueError("Unexpected run start time")
    lines = log.read_text(encoding="utf-8").splitlines()
    observed = []
    for check in CHECKS:
        passed = data["checks"][check]["passed"]
        if not isinstance(passed, bool):
            raise ValueError(f"Missing outcome for {check}")
        line = f"    {'ok  ' if passed else 'FAIL'} {check}"
        if lines.count(line) != 1:
            raise ValueError(f"Run record and terminal output disagree on {check}")
        observed.append(line)
    step = data["steps"][-1]
    reason = "ValueError: This scoring package was built from ADEME's full export: it holds copied ecoinvent blocks"
    if (step["step"] != "dds-build-skeleton" or step["exit"] != 1
            or reason not in (report.parent / "dds-build-skeleton.log").read_text()):
        raise ValueError("The run does not document the full-input export safeguard")
    parity = [line for line in brightway_log.read_text().splitlines() if PARITY_LINE.fullmatch(line)]
    if len(parity) != 1:
        raise ValueError("Expected the local Brightway export parity result")
    scores = data["backtest"]["climate change"]
    return {
        "started": data["started"], "revision": data["adapter_commit"],
        "compared": scores["compared"], "within_5pct": scores["within_5pct"],
        "check_lines": observed, "brightway_parity": parity[0],
        "stripped_export": "refused-licensed-blocks",
    }


def table_row(label, hits, total):
    if not (type(hits) is int and type(total) is int and 0 <= hits <= total and total > 0):
        raise ValueError("Invalid climate result counts")
    verdict = "Passed" if 100 * hits >= 99 * total else "Missed"
    return f"| {label} | {hits:,} of {total:,} ({hits / total:.1%}) | {total - hits:,} | {verdict} |"


def render(snapshot, record):
    if snapshot["revision"] != record["local"]["commit"]:
        raise ValueError("The recorded runs use different adapter revisions")
    step = next(s for s in record["summary"]["steps"] if s["name"] == "Score")
    figures = {f["label"]: f["value"] for f in step["figures"]}
    if snapshot["compared"] != figures["climate scores compared"]:
        raise ValueError("The runs compared different numbers of climate scores")
    table = "\n".join([
        "| AGRIBALYSE 3.2 input | Foods within 5% of ADEME | Outside tolerance | 99% target |",
        "|---|---|---:|---|",
        table_row("Distributable source", figures["climate scores within 5%"], snapshot["compared"]),
        table_row("Full licensed source", snapshot["within_5pct"], snapshot["compared"]),
    ])
    checks = snapshot["check_lines"]
    valid_lines = {f"    {prefix} {check}" for prefix in ("ok  ", "FAIL") for check in CHECKS}
    if len(checks) != len(CHECKS) or any(
        line not in valid_lines or line[9:] != check for line, check in zip(checks, CHECKS)
    ):
        raise ValueError("Unrecognised terminal checks")
    if not checks[0].startswith("    ok") or checks[1].startswith("    ok") != (
        snapshot["within_5pct"] * 100 >= snapshot["compared"] * 99
    ):
        raise ValueError("Full-source selection or measured climate verdict disagrees with the log")
    if snapshot["stripped_export"] != "refused-licensed-blocks" or not PARITY_LINE.fullmatch(snapshot["brightway_parity"]):
        raise ValueError("Missing export verification")
    terminal = "\n".join(html.escape(line) for line in [*checks, snapshot["brightway_parity"]])
    evidence = (f'Run started **{snapshot["started"]}** on revision `{snapshot["revision"][:7]}`. '
                "The local Brightway export passed its sampled score check. The extracts below come from the climate and Brightway runs.\n\n"
                f'<pre tabindex="0"><code>{terminal}</code></pre>')
    return [(ROOT / "site/build.md", "source comparison", table),
            (ROOT / "site/runs.md", "full source checks", evidence)]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--from-run", type=Path, help="private full-source result.json")
    parser.add_argument("--log", type=Path, help="terminal log from the same execution")
    parser.add_argument("--brightway-log", type=Path, help="local Brightway export terminal log")
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args()
    inputs = (args.from_run, args.log, args.brightway_log)
    if any(inputs) and (not all(inputs) or args.check):
        parser.error("Refreshing needs the result and both logs. Use --check separately.")
    snapshot = collect(*inputs) if args.from_run else read(SNAPSHOT)
    pages = render(snapshot, read(ROOT / "site/licensed-run.json"))
    for path, name, content in pages:
        before, start, remaining = path.read_text().partition(f"<!-- {name} -->")
        _, end, after = remaining.partition(f"<!-- end {name} -->")
        if not start or not end:
            raise ValueError(f"Missing {name} marker in {path.name}")
        updated = f"{before}{start}\n\n{content}\n\n{end}{after}"
        if args.check:
            if path.read_text() != updated:
                raise SystemExit(f"Stale {name} in {path.name}")
        else:
            path.write_text(updated)
    if args.from_run:
        SNAPSHOT.write_text(json.dumps(snapshot, indent=2) + "\n")


if __name__ == "__main__":
    main()
