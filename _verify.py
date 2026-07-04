#!/usr/bin/env python3
"""Final verification script."""
import json
import subprocess
import sys

PY = ".venv/bin/python"
errors = 0

# 1. Health check
rc = subprocess.run([PY, "skill/scripts/health_check.py", "tests/fixtures/wikis/populated", "--quiet"],
                    capture_output=True, text=True, timeout=30)
data = json.loads(rc.stdout)
assert data["overall_status"] == "healthy", f"Expected healthy, got {data['overall_status']}"
assert data["exit_code"] == 0
assert len(data["checks"]) == 8
print("PASS: Health check on populated wiki → healthy, 8 checks")

# 2. Check --quiet/--verbose flags exist
for script in ["skill/scripts/ingest.py", "skill/scripts/backup.py", "skill/scripts/lint_wiki.py", "skill/scripts/link_suggest.py"]:
    rc = subprocess.run([PY, script, "--help"], capture_output=True, text=True, timeout=15)
    assert "--quiet" in rc.stdout + rc.stderr, f"{script}: missing --quiet"
    assert "--verbose" in rc.stdout + rc.stderr, f"{script}: missing --verbose"
    print(f"PASS: {script} has --quiet/--verbose flags")

# 3. Verify structured log output
rc = subprocess.run([PY, "-c", """
import sys
sys.path.insert(0, 'skill/scripts')
from wiki_logging import error, set_level
set_level('DEBUG')
error('test', 'verify migration', path='/tmp/test')
"""], capture_output=True, text=True, timeout=15)
log_line = rc.stderr.strip()
parsed = json.loads(log_line)
assert parsed["lvl"] == "ERROR"
assert parsed["cmp"] == "test"
assert parsed["msg"] == "verify migration"
assert parsed["path"] == "/tmp/test"
print("PASS: Structured log output format valid")

# 4. Verify error() produces JSON on stderr (not stdout)
assert rc.stdout.strip() == "" or not rc.stdout.strip().startswith("{"), "stdout should not contain JSON"
print("PASS: Log output goes to stderr, not stdout")

print(f"\n--- {errors} error(s) ---")
sys.exit(0 if errors == 0 else 1)
