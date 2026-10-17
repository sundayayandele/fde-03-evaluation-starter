# starter: verbatim
import importlib.util
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
spec = importlib.util.spec_from_file_location("make_starter", ROOT / "scripts" / "make_starter.py")
make_starter = importlib.util.module_from_spec(spec)
spec.loader.exec_module(make_starter)

PY = '''def f():
    # >>> SOLUTION: week-01 add
    return 1 + 1
    # <<< SOLUTION
'''

MD = """| Metric | Value |
<!-- >>> SOLUTION: week-02 results -->
| F1 | 0.91 |
<!-- <<< SOLUTION -->
"""


def test_python_block_becomes_not_implemented():
    out, n = make_starter.strip_solutions(PY, "py")
    assert n == 1
    assert 'raise NotImplementedError("TODO week-01 add: see labs/")' in out
    assert "1 + 1" not in out


def test_markdown_block_becomes_todo():
    out, n = make_starter.strip_solutions(MD, "md")
    assert n == 1
    assert "0.91" not in out
    assert "TODO week-02 results" in out


def test_module_level_python_marker_rejected():
    with pytest.raises(make_starter.MarkerError, match="function body"):
        make_starter.strip_solutions("# >>> SOLUTION: x\nX = 1\n# <<< SOLUTION\n", "py")


def test_unclosed_block_rejected():
    with pytest.raises(make_starter.MarkerError, match="not closed"):
        make_starter.strip_solutions("def f():\n    # >>> SOLUTION\n    pass\n", "py")


@pytest.mark.skipif((ROOT / ".starter").exists(), reason="starter repos have no solution blocks")
def test_build_whole_repo(tmp_path):
    out = tmp_path / "starter"
    stats = make_starter.build(ROOT, out)
    assert stats["blocks"] >= 1
    assert (out / ".starter").exists()
    assert "Learner starter" in (out / "README.md").read_text()
    assert "Welcome to the FDE series" not in (out / "app" / "main.py").read_text()
    # Files that describe markers are copied verbatim.
    assert (out / "scripts" / "make_starter.py").read_text() == \
        (ROOT / "scripts" / "make_starter.py").read_text()
