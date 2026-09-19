"""Preview or import the bounded GridMend sprint backlog using authenticated gh."""
import argparse
import json
from pathlib import Path
import shutil
import subprocess
import tempfile

REPO = "HackBarna-GridMend/gridmend"
ROOT = Path(__file__).resolve().parents[1]

def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--apply", action="store_true", help="Create missing issues (default previews only)")
    args = parser.parse_args()
    tasks = json.loads((ROOT / "docs/sprint-issues.json").read_text())
    if not args.apply:
        for task in tasks:
            print(task["title"])
        print(f"Preview only: {len(tasks)} tickets. Run with --apply to create missing issues.")
        return
    if not shutil.which("gh"):
        raise SystemExit("GitHub CLI (gh) is required. Install it and authenticate before importing.")
    result = subprocess.run(["gh", "issue", "list", "--repo", REPO, "--state", "all",
                             "--limit", "1000", "--json", "number,title"],
                            check=True, capture_output=True, text=True)
    existing = json.loads(result.stdout)
    if len(existing) >= 1000:
        raise SystemExit("Issue listing reached its limit; review pagination before importing.")
    titles = {item["title"] for item in existing}
    for task in tasks:
        if task["title"] in titles:
            print("Already exists:", task["title"])
            continue
        with tempfile.TemporaryDirectory(prefix="gridmend-issue-") as tmp:
            body = Path(tmp) / "body.md"
            body.write_text(task["body"])
            subprocess.run(["gh", "issue", "create", "--repo", REPO,
                            "--title", task["title"], "--body-file", str(body)], check=True)
        titles.add(task["title"])

if __name__ == "__main__":
    main()
