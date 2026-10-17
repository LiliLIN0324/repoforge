from repoforge.agent.router import route_tier


def test_plan_uses_super_by_default():
    assert route_tier("plan", "fix failing tests") == "super"


def test_hard_plan_uses_ultra():
    assert route_tier("plan", "refactor architecture for concurrency") == "ultra"


def test_explore_uses_nano():
    assert route_tier("explore", "fix failing tests") == "nano"


def test_force_override():
    assert route_tier("explore", "anything", force="ultra") == "ultra"


def test_failures_escalate_reflect():
    assert route_tier("reflect", "fix", failure_count=2) == "super"
