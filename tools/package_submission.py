"""Package the finished coursework and verify its extracted contents."""

import argparse
import hashlib
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import zipfile

ROOT = Path(__file__).resolve().parents[1]


def digest(data):
    return hashlib.sha256(data).hexdigest()


def package(output):
    report = ROOT/"实验二报告.pdf"
    validation = json.loads((ROOT/"results/report_validation.json").read_text(encoding="utf-8"))
    verification = json.loads((ROOT/"results/verification.json").read_text(encoding="utf-8"))
    if validation["pages"] > 5 or validation["pages"] < 1:
        raise ValueError("report exceeds the 5-page limit")
    if digest(report.read_bytes()) != validation["sha256"] or not verification["passed"]:
        raise ValueError("report hash or test verification is invalid; rebuild before packaging")
    skip_dirs = {"__pycache__",".git",".venv","tmp"}
    files = sorted(p for p in ROOT.rglob("*") if p.is_file()
                   and not any(x in skip_dirs for x in p.relative_to(ROOT).parts)
                   and p.suffix.lower() not in (".zip",".rar",".pyc")
                   and p.name != "MANIFEST.sha256")
    if [p for p in files if p.suffix.lower()==".pdf"] != [report]:
        raise ValueError("submission must contain exactly one PDF report")
    manifest = ROOT/"MANIFEST.sha256"
    manifest.write_text("".join(digest(p.read_bytes())+"  "+p.relative_to(ROOT).as_posix()+"\n" for p in files),encoding="utf-8")
    files.append(manifest)
    output.parent.mkdir(parents=True,exist_ok=True)
    with zipfile.ZipFile(output,"w",zipfile.ZIP_DEFLATED,compresslevel=9) as archive:
        for file in files:
            archive.write(file,arcname="experiment2/"+file.relative_to(ROOT).as_posix())
    with zipfile.ZipFile(output) as archive:
        assert archive.testzip() is None, "ZIP CRC check failed"
        assert sum(name.lower().endswith(".pdf") for name in archive.namelist()) == 1
        for line in manifest.read_text(encoding="utf-8").splitlines():
            sha,path = line.split("  ",1)
            assert digest(archive.read("experiment2/"+path)) == sha, "file hash mismatch: "+path
        with tempfile.TemporaryDirectory(prefix="experiment2_submission_check_") as temporary:
            archive.extractall(temporary)
            cwd=Path(temporary)/"experiment2"
            for command in ([sys.executable,"main.py","demo"],
                            [sys.executable,"-m","unittest","discover","-s","tests","-v"]):
                result=subprocess.run(command,cwd=str(cwd),capture_output=True,text=True,encoding="utf-8")
                if result.returncode:
                    raise RuntimeError("extracted submission failed:\n"+result.stdout+result.stderr)
    summary={"zip":str(output.resolve()),"file_count":len(files),"bytes":output.stat().st_size,
             "pdf_count":1,"report_pages":validation["pages"],"github_url":validation["github_url"],
             "zip_crc_passed":True,"manifest_sha256_passed":True,"extracted_demo_and_tests_passed":True,
             "sha256":digest(output.read_bytes())}
    print(json.dumps(summary,ensure_ascii=False,indent=2))


if __name__ == "__main__":
    parser=argparse.ArgumentParser()
    parser.add_argument("--output",type=Path,default=ROOT.parent/"实验二_提交.zip")
    package(parser.parse_args().output)
