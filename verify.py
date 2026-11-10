"""Save auditable sample output and the real unittest log; fail on any error."""

from datetime import datetime, timezone
import json
from pathlib import Path
import platform
import re
import subprocess
import sys


def main():
    root = Path(__file__).resolve().parent
    output = root / "results"
    output.mkdir(exist_ok=True)
    command = [sys.executable, "-m", "unittest", "discover", "-s", "tests", "-v"]
    tests = subprocess.run(command,cwd=str(root),capture_output=True,text=True,encoding="utf-8")
    log = tests.stdout + tests.stderr
    (output/"test_log.txt").write_text(log,encoding="utf-8")
    print(log)
    if tests.returncode:
        raise SystemExit(tests.returncode)
    demo = subprocess.run([sys.executable,"main.py","demo"],cwd=str(root),capture_output=True,text=True,encoding="utf-8")
    if demo.returncode:
        print(demo.stderr)
        raise SystemExit(demo.returncode)
    samples = json.loads(demo.stdout)
    assert samples["official_samples_passed"]
    (output/"official_output.json").write_text(json.dumps(samples,ensure_ascii=False,indent=2),encoding="utf-8")
    match = re.search(r"Ran (\d+) tests",log)
    summary = {"passed":True,"test_methods":int(match.group(1)) if match else None,
               "random_cases":{"mazes":250,"weighted_maps":250,"trees":200,"treasure_games":40},
               "notes":"Each randomized case exercises multiple modes/orders/cache variants; test_methods is unittest methods, not case count.",
               "official_examples_passed":True,"python":platform.python_version(),
               "run_utc":datetime.now(timezone.utc).isoformat()}
    (output/"verification.json").write_text(json.dumps(summary,ensure_ascii=False,indent=2),encoding="utf-8")
    print(json.dumps(summary,ensure_ascii=False))


if __name__ == "__main__":
    main()
