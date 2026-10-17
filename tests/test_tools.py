from pathlib import Path

from repoforge.tools.edit import apply_edit
from repoforge.tools.filesystem import RepoSandbox
from repoforge.tools.search import search_text


def test_list_and_read(tmp_path: Path):
    (tmp_path / "a.py").write_text("x = 1\n", encoding="utf-8")
    sb = RepoSandbox(tmp_path)
    assert "a.py" in sb.list_dir()
    assert "x = 1" in sb.read_file("a.py")


def test_sandbox_escape(tmp_path: Path):
    sb = RepoSandbox(tmp_path)
    try:
        sb.resolve("../outside")
        assert False, "should have raised"
    except PermissionError:
        pass


def test_search_and_edit(tmp_path: Path):
    (tmp_path / "m.py").write_text("def f():\n    return 1\n", encoding="utf-8")
    sb = RepoSandbox(tmp_path)
    hits = search_text(sb, r"return 1")
    assert hits and hits[0].path == "m.py"
    result = apply_edit(sb, "m.py", "return 1", "return 2")
    assert result.applied
    assert "return 2" in sb.read_file("m.py")
