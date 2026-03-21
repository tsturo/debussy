from debussy.config import (
    STAGE_UX_REVIEW, STAGE_PERF_REVIEW,
    STAGE_TO_ROLE, NEXT_STAGE, STAGE_SHORT,
    POST_MERGE_STAGES, STAGE_REQUIRED_TAGS, ACCEPTANCE_ROLES,
    DEFAULTS,
)


def test_ux_review_stage_constant():
    assert STAGE_UX_REVIEW == "ux_review"


def test_perf_review_stage_constant():
    assert STAGE_PERF_REVIEW == "perf_review"


def test_stage_to_role_includes_new_roles():
    assert STAGE_TO_ROLE[STAGE_UX_REVIEW] == "ux-reviewer"
    assert STAGE_TO_ROLE[STAGE_PERF_REVIEW] == "perf-reviewer"


def test_next_stage_merging_goes_to_ux_review():
    assert NEXT_STAGE["merging"] == "ux_review"


def test_next_stage_ux_review_goes_to_perf_review():
    assert NEXT_STAGE["ux_review"] == "perf_review"


def test_next_stage_perf_review_goes_to_done():
    assert NEXT_STAGE["perf_review"] == "done"


def test_stage_short_includes_new_stages():
    assert STAGE_SHORT[STAGE_UX_REVIEW] == "ux"
    assert STAGE_SHORT[STAGE_PERF_REVIEW] == "perf"


def test_post_merge_stages():
    assert "ux_review" in POST_MERGE_STAGES
    assert "perf_review" in POST_MERGE_STAGES
    assert "done" in POST_MERGE_STAGES


def test_stage_required_tags():
    assert STAGE_REQUIRED_TAGS["ux_review"] == "ux_review"
    assert STAGE_REQUIRED_TAGS["perf_review"] == "perf_review"


def test_acceptance_roles():
    assert ACCEPTANCE_ROLES == ["tester", "arch-reviewer", "skeptic"]


def test_defaults_include_new_role_models():
    models = DEFAULTS["role_models"]
    assert "ux-reviewer" in models
    assert "perf-reviewer" in models
    assert "arch-reviewer" in models
    assert "skeptic" in models


def test_defaults_include_new_max_role_agents():
    caps = DEFAULTS["max_role_agents"]
    assert "ux-reviewer" in caps
    assert "perf-reviewer" in caps
    assert "arch-reviewer" in caps
    assert "skeptic" in caps
