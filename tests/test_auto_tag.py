import pytest
from debussy.takt import get_db, init_db, create_task, get_task
from debussy.takt.log import advance_task


@pytest.fixture
def project(tmp_path, monkeypatch):
    (tmp_path / ".git").mkdir()
    init_db(tmp_path)
    monkeypatch.chdir(tmp_path)
    return tmp_path


@pytest.fixture
def db(project):
    with get_db() as conn:
        yield conn


def test_advance_auto_adds_ux_review_when_frontend_present(db):
    task = create_task(db, "UI task", tags=["frontend"])
    advance_task(db, task["id"])  # → development
    updated = get_task(db, task["id"])
    assert "ux_review" in updated["tags"]


def test_advance_does_not_duplicate_ux_review(db):
    task = create_task(db, "UI task", tags=["frontend", "ux_review"])
    advance_task(db, task["id"])
    updated = get_task(db, task["id"])
    assert updated["tags"].count("ux_review") == 1


def test_advance_no_auto_tag_without_frontend(db):
    task = create_task(db, "API task", tags=["perf_review"])
    advance_task(db, task["id"])
    updated = get_task(db, task["id"])
    assert "ux_review" not in updated["tags"]
