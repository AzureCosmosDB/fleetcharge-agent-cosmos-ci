import json
from xml.etree import ElementTree

import pytest

from scripts import ci_report


def junit(path, *, tests=1, failures=0, errors=0, skipped=0):
    path.write_text(
        f'<testsuites><testsuite tests="{tests}" failures="{failures}" '
        f'errors="{errors}" skipped="{skipped}"/></testsuites>'
    )


def live_evidence(path, *, completed=True):
    path.write_text(
        json.dumps(
            {
                "request": {"depotId": "SEA-01", "deliveryWaveId": "wave-test"},
                "reviews": [
                    {
                        "scenario": scenario,
                        "status": 200,
                        "comparison": "exact JSON",
                        "matchesExpected": True,
                        "expected": {"recommendation": "noAction"},
                        "actual": {"recommendation": "noAction"},
                    }
                    for scenario in ("seeded", "updated")
                ],
                "questions": [
                    {
                        "scenario": f"count {count}",
                        "status": 200,
                        "comparison": "count and IDs",
                        "matchesExpected": True,
                        "expected": {"vehicleCount": count},
                        "actual": {"vehicleCount": count, "answer": f"There are {count} vehicles."},
                    }
                    for count in (3, 4)
                ],
                "dispatch": [
                    {
                        "scenario": f"dispatch {bay}",
                        "status": 200,
                        "comparison": "bay and reference",
                        "matchesExpected": True,
                        "expected": {"pickupBay": bay},
                        "actual": {"pickupBay": bay},
                    }
                    for bay in ("BAY-2", "BAY-7")
                ],
                "checks": ["Independent SDK read/query/update/delete"],
                "completed": completed,
            }
        ),
        encoding="utf-8",
    )
    (path.parent / "ollama-model.json").write_text('{"name":"test:latest"}')
    (path.parent / "ollama-inference.json").write_text(
        json.dumps(
            [
                {
                    "completed": True,
                    "model": "test:latest",
                    "responseId": f"call-{index}",
                    "rawResponse": '{"answer":"There are 3 vehicles."}',
                    "messages": [{"role": "user", "text": "Count retrieved vehicle records"}],
                }
                for index in range(20)
            ]
        )
    )


def test_emulator_report_uses_actual_junit_counts(tmp_path):
    junit(tmp_path / "results.xml", tests=133)
    report, passed = ci_report.build_report("emulator", tmp_path)
    assert passed
    assert "| 133 | 0 | 0 | 0 |" in report
    assert "Result: **PASS**" in report


@pytest.mark.parametrize("counts", [{"failures": 1}, {"errors": 1}, {"skipped": 1}, {"tests": 0}])
def test_failed_or_empty_suites_never_report_success(tmp_path, counts):
    junit(tmp_path / "results.xml", **counts)
    report, passed = ci_report.build_report("emulator", tmp_path)
    assert not passed
    assert "Result: **FAIL**" in report


def test_live_report_contains_actual_request_responses_and_sdk_checks(tmp_path):
    junit(tmp_path / "ollama-results.xml")
    live_evidence(tmp_path / "ollama-review-output.json")
    report, passed = ci_report.build_report("ollama", tmp_path)
    assert passed
    assert '"depotId": "SEA-01"' in report
    assert report.count("Actual response:") == 6
    assert "Independent SDK read/query/update/delete" in report
    assert "Completed provider calls: 20" in report
    assert "Raw model completion:" in report
    assert "not a scripted model" in report


@pytest.mark.parametrize("mutation", ["missing", "incomplete", "wrong-model"])
def test_passing_junit_requires_actual_provider_transcript(tmp_path, mutation):
    junit(tmp_path / "ollama-results.xml")
    live_evidence(tmp_path / "ollama-review-output.json")
    path = tmp_path / "ollama-inference.json"
    if mutation == "missing":
        path.unlink()
    else:
        calls = json.loads(path.read_text())
        calls[0]["completed" if mutation == "incomplete" else "model"] = False
        path.write_text(json.dumps(calls))
    with pytest.raises(ValueError, match="actual inference records"):
        ci_report.build_report("ollama", tmp_path)


@pytest.mark.parametrize("missing", [True, False])
def test_passing_live_junit_requires_complete_response_evidence(tmp_path, missing):
    junit(tmp_path / "ollama-results.xml")
    if not missing:
        live_evidence(tmp_path / "ollama-review-output.json", completed=False)
    with pytest.raises(ValueError, match="response evidence"):
        ci_report.build_report("ollama", tmp_path)


def test_failed_live_test_without_response_records_is_explicit(tmp_path):
    junit(tmp_path / "ollama-results.xml", failures=1)
    report, passed = ci_report.build_report("ollama", tmp_path)
    assert not passed
    assert "No response evidence was written" in report


def test_model_text_cannot_close_the_json_fence():
    assert ci_report.json_block({"text": "```"}).startswith("````json\n")


def test_cli_persists_prints_and_publishes_markdown(tmp_path, monkeypatch, capsys):
    artifacts = tmp_path / ".artifacts"
    artifacts.mkdir()
    junit(artifacts / "results.xml")
    summary = tmp_path / "summary.md"
    monkeypatch.setattr(ci_report, "ROOT", tmp_path)
    monkeypatch.setattr("sys.argv", ["ci_report", "--suite", "emulator"])
    monkeypatch.setenv("GITHUB_STEP_SUMMARY", str(summary))
    assert ci_report.main() == 0
    report = (artifacts / "emulator-report.md").read_text(encoding="utf-8")
    assert summary.read_text(encoding="utf-8") == report
    assert report in capsys.readouterr().out


def test_cli_missing_results_fails_explicitly(tmp_path, monkeypatch, capsys):
    monkeypatch.setattr(ci_report, "ROOT", tmp_path)
    monkeypatch.setattr("sys.argv", ["ci_report", "--suite", "emulator"])
    assert ci_report.main() == 1
    assert "FileNotFoundError" in capsys.readouterr().err


def test_malformed_junit_is_not_success(tmp_path):
    (tmp_path / "results.xml").write_text("<bad>")
    with pytest.raises(ElementTree.ParseError):
        ci_report.build_report("emulator", tmp_path)
