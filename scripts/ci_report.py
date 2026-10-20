"""Publish test counts, actual inference and seeded database evidence."""

import argparse
import json
import os
import re
import traceback
from pathlib import Path
from typing import Any
from xml.etree import ElementTree

ROOT = Path(__file__).resolve().parents[1]


def json_block(value: Any) -> str:
    text = json.dumps(value, indent=2, sort_keys=True)
    fence = "`" * max(3, 1 + max((len(run) for run in re.findall(r"`+", text)), default=0))
    return f"{fence}json\n{text}\n{fence}"


def build_report(suite: str, artifacts: Path) -> tuple[str, bool]:
    filename = "results.xml" if suite == "emulator" else "ollama-results.xml"
    root = ElementTree.parse(artifacts / filename).getroot()
    suites = [root] if root.tag == "testsuite" else list(root.findall("testsuite"))
    if not suites:
        raise ValueError("JUnit contains no test suites")
    counts = {
        key: sum(int(item.attrib[key]) for item in suites)
        for key in ("tests", "failures", "errors", "skipped")
    }
    passed = counts["failures"] == counts["errors"] == 0 and counts["tests"] > counts["skipped"]
    lines = [
        f"# FleetCharge {'emulator' if suite == 'emulator' else 'live Ollama'} CI",
        "",
        f"Result: **{'PASS' if passed else 'FAIL'}**",
        "",
        "| Tests | Failures | Errors | Skipped |",
        "|---|---|---|---|",
        "| " + " | ".join(str(counts[key]) for key in counts) + " |",
        "",
    ]
    if suite == "ollama":
        evidence_path = artifacts / "ollama-review-output.json"
        if not evidence_path.exists():
            if passed:
                raise ValueError("Passing live tests must publish actual response evidence")
            lines.append(
                "No response evidence was written. Inspect the failed test and service logs."
            )
        else:
            evidence = json.loads(evidence_path.read_text(encoding="utf-8"))
            reviews = evidence["reviews"]
            questions = evidence["questions"]
            dispatch = evidence["dispatch"]
            if passed and (
                evidence["completed"] is not True
                or len(reviews) != 2
                or len(questions) != 2
                or len(dispatch) != 2
                or any(
                    item["status"] != 200 or item["matchesExpected"] is not True
                    for item in [*dispatch, *questions, *reviews]
                )
            ):
                raise ValueError("Passing live JUnit does not match complete response evidence")
            transcript_path = artifacts / "ollama-inference.json"
            transcript = (
                json.loads(transcript_path.read_text(encoding="utf-8"))
                if transcript_path.exists()
                else []
            )
            model_path = artifacts / "ollama-model.json"
            model = (
                json.loads(model_path.read_text(encoding="utf-8")) if model_path.exists() else {}
            )
            if passed and (
                len(transcript) != 20
                or not model.get("name")
                or any(
                    item.get("completed") is not True
                    or item.get("model") != model["name"]
                    or not item.get("responseId")
                    or not item.get("rawResponse")
                    for item in transcript
                )
            ):
                raise ValueError("Passing live tests require 20 completed actual inference records")
            lines.extend(
                [
                    "## Real model evidence",
                    "",
                    f"Selected model: `{model.get('name', 'unavailable')}`. "
                    f"Completed provider calls: {sum(item['completed'] for item in transcript)}.",
                    "",
                    "The application uses actual Ollama inference, not a scripted model. "
                    "Only the database inputs are seeded test data.",
                    "",
                    "Raw provider inputs, outputs, response IDs and timings are saved in "
                    "`ollama-inference.json`, before tool-adapter conversion.",
                    "",
                ]
            )
            for index, call in enumerate(transcript[:4], 1):
                lines.extend(
                    [
                        f"### Grounded question {index}: actual provider prompt",
                        "",
                        json_block(call["messages"]),
                        "",
                        "Raw model completion:",
                        "",
                        json_block(call.get("rawResponse")),
                        "",
                    ]
                )
            lines.extend(
                [
                    "## Test request",
                    "",
                    "The agent receives this request and actual tool results, "
                    "not the golden answer.",
                    "",
                    json_block(evidence["request"]),
                    "",
                ]
            )
            for review in [*dispatch, *questions, *reviews]:
                lines.extend(
                    [
                        f"## {review['scenario']}",
                        "",
                        f"HTTP status: {review['status']}. Comparison: {review['comparison']}. "
                        f"Matches expected: {review['matchesExpected']}.",
                        "",
                        "Request:",
                        "",
                        json_block(review.get("request", evidence["request"])),
                        "",
                        "Expected:",
                        "",
                        json_block(review["expected"]),
                        "",
                        "Actual response:",
                        "",
                        json_block(review["actual"]),
                        "",
                    ]
                )
            lines.extend(["## Verified SDK checks", ""])
            lines.extend(f"- {check}" for check in evidence["checks"])
            lines.extend(
                [
                    "",
                    f"All response and SDK assertions completed: {evidence['completed']}.",
                    "",
                    "Seeded records are synthetic test inputs. Responses are generated by the "
                    "real local model; expected values are used only by test assertions.",
                ]
            )
    return "\n".join(lines) + "\n", passed


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--suite", choices=("emulator", "ollama"), required=True)
    args = parser.parse_args()
    try:
        artifacts = ROOT / ".artifacts"
        report, passed = build_report(args.suite, artifacts)
        (artifacts / f"{args.suite}-report.md").write_text(report, encoding="utf-8")
        if summary := os.environ.get("GITHUB_STEP_SUMMARY"):
            with Path(summary).open("a", encoding="utf-8") as output:
                output.write(report)
        print(report, flush=True)
        return 0 if passed else 1
    except (OSError, ValueError, KeyError, TypeError, ElementTree.ParseError):
        traceback.print_exc()
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
