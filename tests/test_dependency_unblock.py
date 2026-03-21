from debussy.takt import get_db, init_db, create_task, update_task
from debussy.takt.log import get_unresolved_deps
import pytest


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


def test_dep_resolved_when_done(db):
    t1 = create_task(db, "First")
    t2 = create_task(db, "Second", deps=[t1["id"]])
    update_task(db, t1["id"], stage="done")
    assert get_unresolved_deps(db, t2["id"]) == []


def test_dep_resolved_when_ux_review(db):
    t1 = create_task(db, "First")
    t2 = create_task(db, "Second", deps=[t1["id"]])
    update_task(db, t1["id"], stage="ux_review")
    assert get_unresolved_deps(db, t2["id"]) == []


def test_dep_resolved_when_perf_review(db):
    t1 = create_task(db, "First")
    t2 = create_task(db, "Second", deps=[t1["id"]])
    update_task(db, t1["id"], stage="perf_review")
    assert get_unresolved_deps(db, t2["id"]) == []


def test_dep_unresolved_when_merging(db):
    t1 = create_task(db, "First")
    t2 = create_task(db, "Second", deps=[t1["id"]])
    update_task(db, t1["id"], stage="merging")
    assert get_unresolved_deps(db, t2["id"]) == [t1["id"]]


def test_dep_unresolved_when_reviewing(db):
    t1 = create_task(db, "First")
    t2 = create_task(db, "Second", deps=[t1["id"]])
    update_task(db, t1["id"], stage="reviewing")
    assert get_unresolved_deps(db, t2["id"]) == [t1["id"]]
