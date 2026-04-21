"""Unit tests for Python simulator command execution."""

from pathlib import Path

from src.core.python_simulator import PythonSimulator


def test_run_python_script_with_cli_params(tmp_path: Path):
    script_path = tmp_path / "script.py"
    script_path.write_text(
        "import argparse, json\n"
        "parser=argparse.ArgumentParser()\n"
        "parser.add_argument('--value', required=True)\n"
        "args=parser.parse_args()\n"
        "print(json.dumps({'value': args.value, 'status':'ok'}))\n",
        encoding="utf-8",
    )

    simulator = PythonSimulator()
    result = simulator.run(script_path, {"value": "42"}, outputs=["value"]) 

    assert result["exit_code"] == 0
    assert result["outputs"] == {"value": "42"}
    assert result["stderr"] == ""
    assert result["command"][0].endswith("python") or result["command"][0].endswith("python3")


def test_run_non_zero_exit_raises(tmp_path: Path):
    script_path = tmp_path / "fail.py"
    script_path.write_text("raise SystemExit(3)\n", encoding="utf-8")

    simulator = PythonSimulator()

    try:
        simulator.run(script_path, {})
        assert False, "Expected exception"
    except Exception as exc:  # pylint: disable=broad-exception-caught
        assert "Command exited with code" in str(exc)
