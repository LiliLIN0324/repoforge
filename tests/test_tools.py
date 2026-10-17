from pathlib import Path

from repoforge.tools.edit import apply_edit
from repoforge.tools.filesystem import RepoSandbox
from repoforge.tools.search import search_text
from repoforge.tools.tests import run_tests


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


def test_run_tests_cwd_is_sandbox_not_parent_pyproject(tmp_path: Path):
    """Parent pyproject testpaths must not steal collection from the sandbox."""
    parent = tmp_path / "pkg"
    demo = parent / "demo_repo"
    (parent / "tests").mkdir(parents=True)
    demo.mkdir()
    (parent / "pyproject.toml").write_text(
        "[tool.pytest.ini_options]\n"
        "testpaths = ['tests']\n"
        "pythonpath = ['src']\n",
        encoding="utf-8",
    )
    (parent / "tests" / "test_parent.py").write_text(
        "def test_parent_only():\n    assert True\n",
        encoding="utf-8",
    )
    (demo / "test_sandbox_root.py").write_text(
        "from pathlib import Path\n\n"
        "def test_sandbox_root(pytestconfig):\n"
        "    here = Path(__file__).resolve().parent\n"
        "    (here / 'cwd_ok.txt').write_text(str(Path.cwd().resolve()), encoding='utf-8')\n"
        "    assert Path.cwd().resolve() == here\n"
        "    assert Path(str(pytestconfig.rootpath)).resolve() == here\n"
        "    assert list(pytestconfig.getini('testpaths')) != ['tests']\n",
        encoding="utf-8",
    )
    result = run_tests(RepoSandbox(demo), "pytest -q")
    assert result.passed, result.summary()
    assert (demo / "cwd_ok.txt").is_file()
    assert "test_parent_only" not in (result.stdout + result.stderr)
