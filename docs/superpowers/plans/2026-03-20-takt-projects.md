# Takt Multi-Project Support Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add multi-project support to takt so tasks can be namespaced by effort (e.g. `PKL-*`, `FIX-*`) with per-project sequence counters.

**Architecture:** New `projects` table replaces `prefix`/`next_seq` in `metadata`. Migration moves existing data. `generate_id()` and `get_prefix()` rewritten to use `projects`. New `takt project` CLI subcommand. Existing `takt prefix` becomes deprecated alias.

**Tech Stack:** Python, SQLite, pytest

**Spec:** `docs/superpowers/specs/2026-03-20-takt-projects-design.md`

---

### Task 1: Schema and migration

**Files:**
- Modify: `src/debussy/takt/db.py`
- Test: `tests/test_takt_db.py`

- [ ] **Step 1: Write migration test — fresh DB gets projects table**

```python
# tests/test_takt_db.py — add to TestSchema class

def test_projects_table_exists(self, db_dir):
    with get_db(db_dir) as conn:
        tables = {row[0] for row in conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table'"
        ).fetchall()}
        assert "projects" in tables

def test_projects_default_index(self, db_dir):
    with get_db(db_dir) as conn:
        indexes = {row[0] for row in conn.execute(
            "SELECT name FROM sqlite_master WHERE type='index'"
        ).fetchall()}
        assert "idx_projects_default" in indexes
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_takt_db.py::TestSchema::test_projects_table_exists tests/test_takt_db.py::TestSchema::test_projects_default_index -v`
Expected: FAIL — table "projects" not found

- [ ] **Step 3: Add projects table to SCHEMA_SQL and bump version**

In `src/debussy/takt/db.py`, add to `SCHEMA_SQL` (after the log index):

```sql
CREATE TABLE IF NOT EXISTS projects (
    prefix     TEXT PRIMARY KEY CHECK(length(prefix) BETWEEN 2 AND 5),
    name       TEXT NOT NULL,
    is_default INTEGER NOT NULL DEFAULT 0,
    next_seq   INTEGER NOT NULL DEFAULT 1
);
CREATE UNIQUE INDEX IF NOT EXISTS idx_projects_default ON projects(is_default) WHERE is_default = 1;
```

Change `SCHEMA_VERSION = 2` to `SCHEMA_VERSION = 3`.

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest tests/test_takt_db.py::TestSchema::test_projects_table_exists tests/test_takt_db.py::TestSchema::test_projects_default_index -v`
Expected: PASS

- [ ] **Step 5: Write migration test — v2 DB migrates to v3**

```python
# tests/test_takt_db.py — new class

class TestMigrationV2ToV3:
    def test_migrates_prefix_to_projects(self, db_dir):
        """A v2 database with prefix in metadata gets migrated to projects table."""
        import sqlite3
        takt_dir = db_dir / ".takt"
        takt_dir.mkdir()
        db_path = takt_dir / "takt.db"
        conn = sqlite3.connect(str(db_path))
        conn.execute("CREATE TABLE metadata (key TEXT PRIMARY KEY, value TEXT NOT NULL)")
        conn.execute("INSERT INTO metadata (key, value) VALUES ('prefix', 'PKL')")
        conn.execute("INSERT INTO metadata (key, value) VALUES ('next_seq', '5')")
        conn.execute("PRAGMA user_version = 2")
        conn.commit()
        conn.close()

        with get_db(db_dir) as conn:
            conn.row_factory = sqlite3.Row
            row = conn.execute(
                "SELECT * FROM projects WHERE is_default = 1"
            ).fetchone()
            assert row is not None
            assert row["prefix"] == "PKL"
            assert row["next_seq"] == 5
            old = conn.execute(
                "SELECT * FROM metadata WHERE key = 'prefix'"
            ).fetchone()
            assert old is None
            old_seq = conn.execute(
                "SELECT * FROM metadata WHERE key = 'next_seq'"
            ).fetchone()
            assert old_seq is None

    def test_migration_is_atomic(self, db_dir):
        """Schema version only bumps after successful migration."""
        import sqlite3
        takt_dir = db_dir / ".takt"
        takt_dir.mkdir()
        db_path = takt_dir / "takt.db"
        conn = sqlite3.connect(str(db_path))
        conn.execute("CREATE TABLE metadata (key TEXT PRIMARY KEY, value TEXT NOT NULL)")
        conn.execute("INSERT INTO metadata (key, value) VALUES ('prefix', 'ABC')")
        conn.execute("INSERT INTO metadata (key, value) VALUES ('next_seq', '3')")
        conn.execute("PRAGMA user_version = 2")
        conn.commit()
        conn.close()

        with get_db(db_dir) as conn:
            version = conn.execute("PRAGMA user_version").fetchone()[0]
            assert version == SCHEMA_VERSION
```

- [ ] **Step 6: Run test to verify it fails**

Run: `python -m pytest tests/test_takt_db.py::TestMigrationV2ToV3 -v`
Expected: FAIL — no migration logic yet

- [ ] **Step 7: Implement migration in `_migrate()`**

In `src/debussy/takt/db.py`, add v2→v3 migration block inside `_migrate()`. Note: `_migrate()` runs before `executescript(SCHEMA_SQL)`, so we must create the table and index inline.

```python
if version < 3:
    conn.execute(
        "CREATE TABLE IF NOT EXISTS projects ("
        "prefix TEXT PRIMARY KEY CHECK(length(prefix) BETWEEN 2 AND 5), "
        "name TEXT NOT NULL, "
        "is_default INTEGER NOT NULL DEFAULT 0, "
        "next_seq INTEGER NOT NULL DEFAULT 1)"
    )
    conn.execute(
        "CREATE UNIQUE INDEX IF NOT EXISTS idx_projects_default "
        "ON projects(is_default) WHERE is_default = 1"
    )
    tables = [r[0] for r in conn.execute(
        "SELECT name FROM sqlite_master WHERE type='table'"
    ).fetchall()]
    if "metadata" in tables:
        prefix_row = conn.execute(
            "SELECT value FROM metadata WHERE key = 'prefix'"
        ).fetchone()
        seq_row = conn.execute(
            "SELECT value FROM metadata WHERE key = 'next_seq'"
        ).fetchone()
        if prefix_row:
            prefix = prefix_row[0] if isinstance(prefix_row, tuple) else prefix_row["value"]
            next_seq = int(seq_row[0] if isinstance(seq_row, tuple) else seq_row["value"]) if seq_row else 1
            conn.execute(
                "INSERT OR IGNORE INTO projects (prefix, name, is_default, next_seq) "
                "VALUES (?, ?, 1, ?)",
                (prefix, prefix, next_seq),
            )
            conn.execute("DELETE FROM metadata WHERE key = 'prefix'")
            conn.execute("DELETE FROM metadata WHERE key = 'next_seq'")
```

- [ ] **Step 8: Run migration tests**

Run: `python -m pytest tests/test_takt_db.py::TestMigrationV2ToV3 -v`
Expected: PASS

- [ ] **Step 9: Run full db test suite**

Run: `python -m pytest tests/test_takt_db.py -v`
Expected: ALL PASS

- [ ] **Step 10: Commit**

```bash
git add src/debussy/takt/db.py tests/test_takt_db.py
git commit -m "[takt] Add projects table schema and v2→v3 migration"
```

---

### Task 2: Rewrite `get_prefix()`, `_ensure_prefix()`, `generate_id()`

**Files:**
- Modify: `src/debussy/takt/db.py` (lines 73-88: `get_prefix`, `_ensure_prefix`)
- Modify: `src/debussy/takt/models.py` (lines 11-22: `generate_id`)
- Test: `tests/test_takt_models.py`
- Test: `tests/test_takt_db.py`

- [ ] **Step 1: Write test for `get_prefix()` reading from projects table**

```python
# tests/test_takt_db.py — new class

class TestGetPrefix:
    def test_returns_default_project_prefix(self, db_dir):
        with get_db(db_dir) as conn:
            prefix = get_prefix(conn)
            assert len(prefix) >= 2
            assert prefix.isalpha()
            assert prefix.isupper()

    def test_errors_when_no_default_project(self, db_dir):
        with get_db(db_dir) as conn:
            conn.execute("DELETE FROM projects")
            with pytest.raises(RuntimeError):
                get_prefix(conn)
```

- [ ] **Step 2: Run test to verify behavior**

Run: `python -m pytest tests/test_takt_db.py::TestGetPrefix -v`
Expected: `test_returns_default_project_prefix` may pass (current impl reads metadata which is now empty after migration — might return "TSK"). `test_errors_when_no_default_project` will fail (current impl returns "TSK" instead of raising).

- [ ] **Step 3: Rewrite `get_prefix()` and `_ensure_prefix()`**

In `src/debussy/takt/db.py`:

Replace `get_prefix`:
```python
def get_prefix(conn: sqlite3.Connection) -> str:
    row = conn.execute(
        "SELECT prefix FROM projects WHERE is_default = 1"
    ).fetchone()
    if row is None:
        raise RuntimeError("No default project. Run: takt project add <PREFIX> <NAME> --default")
    return row["prefix"]
```

Replace `_ensure_prefix` with `_ensure_default_project`:
```python
def _ensure_default_project(conn: sqlite3.Connection, project_dir: Path) -> None:
    row = conn.execute("SELECT 1 FROM projects LIMIT 1").fetchone()
    if row is None:
        prefix = _derive_prefix(project_dir)
        conn.execute(
            "INSERT INTO projects (prefix, name, is_default, next_seq) VALUES (?, ?, 1, 1)",
            (prefix, prefix),
        )
```

In `get_db()`, change `_ensure_prefix(conn, root)` to `_ensure_default_project(conn, root)`.

- [ ] **Step 4: Run get_prefix tests**

Run: `python -m pytest tests/test_takt_db.py::TestGetPrefix -v`
Expected: PASS

- [ ] **Step 5: Write test for `generate_id()` with project prefix**

```python
# tests/test_takt_models.py — add to TestGenerateId class

def test_with_explicit_prefix(self, db):
    db.execute(
        "INSERT INTO projects (prefix, name, is_default, next_seq) VALUES ('FIX', 'Fixes', 0, 1)"
    )
    tid, seq = generate_id(db, prefix="FIX")
    assert tid == "FIX-1"
    assert seq == 1

def test_explicit_prefix_independent_sequence(self, db):
    db.execute(
        "INSERT INTO projects (prefix, name, is_default, next_seq) VALUES ('FIX', 'Fixes', 0, 1)"
    )
    default_id, _ = generate_id(db)
    fix_id, _ = generate_id(db, prefix="FIX")
    assert fix_id == "FIX-1"
    assert default_id.endswith("-1")

def test_unknown_prefix_errors(self, db):
    with pytest.raises(RuntimeError, match="not found"):
        generate_id(db, prefix="ZZZ")
```

- [ ] **Step 6: Run test to verify it fails**

Run: `python -m pytest tests/test_takt_models.py::TestGenerateId::test_with_explicit_prefix tests/test_takt_models.py::TestGenerateId::test_unknown_prefix_errors -v`
Expected: FAIL — generate_id doesn't accept prefix param

- [ ] **Step 7: Rewrite `generate_id()`**

In `src/debussy/takt/models.py`:

```python
def generate_id(db: sqlite3.Connection, prefix: str | None = None) -> tuple[str, int]:
    if prefix is None:
        prefix = get_prefix(db)
    row = db.execute(
        "UPDATE projects SET next_seq = next_seq + 1 WHERE prefix = ? RETURNING next_seq - 1",
        (prefix,),
    ).fetchone()
    if row is None:
        raise RuntimeError(f"Project not found: {prefix}")
    seq = row[0]
    task_id = f"{prefix}-{seq}"
    return task_id, seq
```

- [ ] **Step 8: Run all model tests**

Run: `python -m pytest tests/test_takt_models.py -v`
Expected: ALL PASS

- [ ] **Step 9: Run full test suite to check nothing broke**

Run: `python -m pytest tests/ -v`
Expected: ALL PASS

- [ ] **Step 10: Commit**

```bash
git add src/debussy/takt/db.py src/debussy/takt/models.py tests/test_takt_db.py tests/test_takt_models.py
git commit -m "[takt] Rewrite get_prefix, generate_id to use projects table"
```

---

### Task 3: `takt project` CLI subcommand

**Files:**
- Modify: `src/debussy/takt/cli.py`
- Test: `tests/test_takt_cli.py`

- [ ] **Step 1: Write tests for `takt project add`**

```python
# tests/test_takt_cli.py — new class

class TestProject:
    def test_add(self, project_dir, capsys):
        assert main(["project", "add", "FIX", "Hotfixes"]) == 0
        assert "FIX" in capsys.readouterr().out

    def test_add_default(self, project_dir, capsys):
        assert main(["project", "add", "FIX", "Hotfixes", "--default"]) == 0
        assert main(["project", "list"]) == 0
        out = capsys.readouterr().out
        assert "FIX" in out

    def test_add_invalid_prefix(self, project_dir):
        assert main(["project", "add", "X", "Too short"]) == 1

    def test_add_duplicate(self, project_dir):
        main(["project", "add", "FIX", "Hotfixes"])
        assert main(["project", "add", "FIX", "Again"]) == 1
```

- [ ] **Step 2: Run to verify failure**

Run: `python -m pytest tests/test_takt_cli.py::TestProject -v`
Expected: FAIL — no "project" subcommand

- [ ] **Step 3: Write tests for `takt project list`, `default`, `rm`**

```python
# tests/test_takt_cli.py — add to TestProject class

def test_list(self, project_dir, capsys):
    main(["project", "add", "FIX", "Hotfixes"])
    capsys.readouterr()
    assert main(["project", "list"]) == 0
    out = capsys.readouterr().out
    assert "FIX" in out

def test_default_switch(self, project_dir, capsys):
    main(["project", "add", "FIX", "Hotfixes"])
    capsys.readouterr()
    assert main(["project", "default", "FIX"]) == 0
    assert main(["project", "list"]) == 0
    out = capsys.readouterr().out
    assert "FIX" in out

def test_default_show(self, project_dir, capsys):
    assert main(["project", "default"]) == 0
    out = capsys.readouterr().out.strip()
    assert out.isalpha() and out.isupper()

def test_rm(self, project_dir, capsys):
    main(["project", "add", "FIX", "Hotfixes"])
    capsys.readouterr()
    assert main(["project", "rm", "FIX"]) == 0

def test_rm_with_tasks_fails(self, project_dir, capsys):
    main(["project", "default"])
    orig = capsys.readouterr().out.strip()
    main(["project", "add", "FIX", "Hotfixes", "--default"])
    capsys.readouterr()
    main(["create", "A task"])
    capsys.readouterr()
    main(["project", "default", orig])
    capsys.readouterr()
    assert main(["project", "rm", "FIX"]) == 1

def test_rm_default_fails(self, project_dir, capsys):
    main(["project", "default"])
    prefix = capsys.readouterr().out.strip()
    assert main(["project", "rm", prefix]) == 1
```

- [ ] **Step 4: Implement `takt project` subcommand**

In `src/debussy/takt/cli.py`, add to `_build_parser()`:

```python
p_project = sub.add_parser("project", help="Manage projects")
project_sub = p_project.add_subparsers(dest="project_command")

p_proj_add = project_sub.add_parser("add", help="Add a project")
p_proj_add.add_argument("prefix", help="2-5 uppercase letters")
p_proj_add.add_argument("name", help="Human-readable name")
p_proj_add.add_argument("--default", action="store_true")

project_sub.add_parser("list", help="List projects")

p_proj_default = project_sub.add_parser("default", help="Show or switch default project")
p_proj_default.add_argument("prefix", nargs="?", help="Switch default to this prefix")

p_proj_rm = project_sub.add_parser("rm", help="Remove a project")
p_proj_rm.add_argument("prefix")
```

In `_dispatch()`, add the handler:

```python
if cmd == "project":
    return _handle_project(args, db)
```

Add `_handle_project` function:

```python
def _handle_project(args: argparse.Namespace, db) -> int:
    sub = args.project_command

    if sub == "add":
        prefix = args.prefix.upper()
        if not prefix.isalpha() or not (2 <= len(prefix) <= 5):
            print("Prefix must be 2-5 letters", file=sys.stderr)
            return 1
        existing = db.execute("SELECT 1 FROM projects WHERE prefix = ?", (prefix,)).fetchone()
        if existing:
            print(f"Project {prefix} already exists", file=sys.stderr)
            return 1
        next_seq = 1
        max_row = db.execute(
            "SELECT MAX(CAST(SUBSTR(id, ?) AS INTEGER)) FROM tasks WHERE id LIKE ?",
            (len(prefix) + 2, f"{prefix}-%"),
        ).fetchone()
        if max_row and max_row[0] is not None:
            next_seq = max_row[0] + 1
        if args.default:
            db.execute("UPDATE projects SET is_default = 0 WHERE is_default = 1")
        has_any = db.execute("SELECT 1 FROM projects LIMIT 1").fetchone()
        is_default = 1 if (args.default or not has_any) else 0
        db.execute(
            "INSERT INTO projects (prefix, name, is_default, next_seq) VALUES (?, ?, ?, ?)",
            (prefix, args.name, is_default, next_seq),
        )
        marker = " (default)" if is_default else ""
        print(f"Added project: {prefix} — {args.name}{marker}")
        return 0

    if sub == "list":
        rows = db.execute(
            "SELECT p.prefix, p.name, p.is_default, p.next_seq, "
            "(SELECT COUNT(*) FROM tasks WHERE id LIKE p.prefix || '-%') AS task_count "
            "FROM projects p ORDER BY p.is_default DESC, p.prefix"
        ).fetchall()
        if not rows:
            print("No projects.")
            return 0
        for r in rows:
            default = " *" if r["is_default"] else ""
            print(f"{r['prefix']}{default}  {r['name']}  ({r['task_count']} tasks)")
        return 0

    if sub == "default":
        if args.prefix:
            prefix = args.prefix.upper()
            row = db.execute("SELECT 1 FROM projects WHERE prefix = ?", (prefix,)).fetchone()
            if not row:
                print(f"Project not found: {prefix}", file=sys.stderr)
                return 1
            db.execute("UPDATE projects SET is_default = 0 WHERE is_default = 1")
            db.execute("UPDATE projects SET is_default = 1 WHERE prefix = ?", (prefix,))
            print(f"Default project: {prefix}")
        else:
            print(get_prefix(db))
        return 0

    if sub == "rm":
        prefix = args.prefix.upper()
        is_default = db.execute(
            "SELECT is_default FROM projects WHERE prefix = ?", (prefix,)
        ).fetchone()
        if not is_default:
            print(f"Project not found: {prefix}", file=sys.stderr)
            return 1
        if is_default["is_default"]:
            print("Cannot remove default project. Switch default first.", file=sys.stderr)
            return 1
        has_tasks = db.execute(
            "SELECT 1 FROM tasks WHERE id LIKE ?", (f"{prefix}-%",)
        ).fetchone()
        if has_tasks:
            print(f"Cannot remove {prefix}: tasks still reference it", file=sys.stderr)
            return 1
        db.execute("DELETE FROM projects WHERE prefix = ?", (prefix,))
        print(f"Removed project: {prefix}")
        return 0

    print("Usage: takt project {add,list,default,rm}", file=sys.stderr)
    return 1
```

- [ ] **Step 5: Run project CLI tests**

Run: `python -m pytest tests/test_takt_cli.py::TestProject -v`
Expected: ALL PASS

- [ ] **Step 6: Commit**

```bash
git add src/debussy/takt/cli.py tests/test_takt_cli.py
git commit -m "[takt] Add takt project subcommand (add, list, default, rm)"
```

---

### Task 4: Deprecate `takt prefix`, add `-p` to create/list

**Files:**
- Modify: `src/debussy/takt/cli.py`
- Modify: `src/debussy/takt/models.py` (add `prefix` param to `create_task`)
- Modify: `src/debussy/takt/models.py` (add `prefix` param to `list_tasks`)
- Test: `tests/test_takt_cli.py`

- [ ] **Step 1: Write tests for deprecated `takt prefix`**

```python
# tests/test_takt_cli.py — new class

class TestPrefixDeprecated:
    def test_prefix_show_still_works(self, project_dir, capsys):
        assert main(["prefix"]) == 0
        out = capsys.readouterr()
        assert out.out.strip().isalpha()
        assert "deprecated" in out.err.lower()

    def test_prefix_set_still_works(self, project_dir, capsys):
        main(["project", "add", "NEW", "New project"])
        capsys.readouterr()
        assert main(["prefix", "NEW"]) == 0
        err = capsys.readouterr().err
        assert "deprecated" in err.lower()

    def test_prefix_set_nonexistent_fails(self, project_dir):
        assert main(["prefix", "ZZZ"]) == 1
```

- [ ] **Step 2: Write tests for `takt create -p` and `takt list -p`**

```python
# tests/test_takt_cli.py — add to TestCreate class

def test_with_project(self, project_dir, capsys):
    main(["project", "add", "FIX", "Fixes"])
    capsys.readouterr()
    assert main(["create", "Fix bug", "-p", "FIX"]) == 0
    task_id = capsys.readouterr().out.strip()
    assert task_id.startswith("FIX-")

def test_with_unknown_project(self, project_dir):
    assert main(["create", "Fix bug", "-p", "ZZZ"]) == 1

def test_cross_project_deps(self, project_dir, capsys):
    main(["create", "Default task"])
    default_id = capsys.readouterr().out.strip()
    main(["project", "add", "FIX", "Fixes"])
    capsys.readouterr()
    main(["create", "Fix task", "-p", "FIX", "--deps", default_id])
    fix_id = capsys.readouterr().out.strip()
    main(["show", fix_id, "--json"])
    data = json.loads(capsys.readouterr().out)
    assert default_id in data["dependencies"]
```

```python
# tests/test_takt_cli.py — add to TestList class

def test_filter_project(self, project_dir, capsys):
    main(["create", "Default task"])
    capsys.readouterr()
    main(["project", "add", "FIX", "Fixes"])
    capsys.readouterr()
    main(["create", "Fix task", "-p", "FIX"])
    capsys.readouterr()
    assert main(["list", "-p", "FIX", "--json"]) == 0
    data = json.loads(capsys.readouterr().out)
    assert len(data) == 1
    assert data[0]["title"] == "Fix task"
```

- [ ] **Step 3: Run tests to verify failure**

Run: `python -m pytest tests/test_takt_cli.py::TestPrefixDeprecated tests/test_takt_cli.py::TestCreate::test_with_project tests/test_takt_cli.py::TestList::test_filter_project -v`
Expected: FAIL

- [ ] **Step 4: Add `prefix` param to `create_task` and `list_tasks`**

In `src/debussy/takt/models.py`, update `create_task`:

```python
def create_task(
    db: sqlite3.Connection,
    title: str,
    description: str = "",
    tags: list[str] | None = None,
    deps: list[str] | None = None,
    prefix: str | None = None,
) -> dict:
    task_id, seq = generate_id(db, prefix=prefix)
    # ... rest unchanged
```

Update `list_tasks` to accept `prefix`:

```python
def list_tasks(
    db: sqlite3.Connection,
    stage: str | None = None,
    status: str | None = None,
    tag: str | None = None,
    prefix: str | None = None,
) -> list[dict]:
    conditions = []
    params: list[str] = []

    if prefix is not None:
        conditions.append("id LIKE ?")
        params.append(f"{prefix}-%")
    # ... rest of existing filter logic unchanged
```

- [ ] **Step 5: Update CLI — deprecate prefix, add -p flags**

In `_dispatch()`, update the `prefix` command handler:

```python
if cmd == "prefix":
    import warnings
    print("Warning: 'takt prefix' is deprecated. Use 'takt project default' instead.", file=sys.stderr)
    if args.value:
        val = args.value.upper()
        row = db.execute("SELECT 1 FROM projects WHERE prefix = ?", (val,)).fetchone()
        if not row:
            print(f"Project not found: {val}", file=sys.stderr)
            return 1
        db.execute("UPDATE projects SET is_default = 0 WHERE is_default = 1")
        db.execute("UPDATE projects SET is_default = 1 WHERE prefix = ?", (val,))
        print(f"Default project: {val}")
    else:
        print(get_prefix(db))
    return 0
```

In `_build_parser()`, add `-p` to create and list:

```python
# In p_create definition, add:
p_create.add_argument("-p", "--project", help="Project prefix")

# In p_list definition, add:
p_list.add_argument("-p", "--project", help="Filter by project prefix")
```

In `_dispatch()`, update create and list handlers to pass prefix:

```python
# create handler:
task = create_task(db, args.title, description=args.description,
                   tags=tags, deps=deps, prefix=args.project)

# list handler:
tasks = list_tasks(db, stage=args.stage, status=args.status, tag=args.tag,
                   prefix=args.project)
```

- [ ] **Step 6: Run all new tests**

Run: `python -m pytest tests/test_takt_cli.py::TestPrefixDeprecated tests/test_takt_cli.py::TestCreate::test_with_project tests/test_takt_cli.py::TestCreate::test_with_unknown_project tests/test_takt_cli.py::TestList::test_filter_project -v`
Expected: PASS

- [ ] **Step 7: Run full test suite**

Run: `python -m pytest tests/ -v`
Expected: ALL PASS

- [ ] **Step 8: Commit**

```bash
git add src/debussy/takt/cli.py src/debussy/takt/models.py tests/test_takt_cli.py
git commit -m "[takt] Deprecate takt prefix, add -p flag to create and list"
```

---

### Task 5: Board filtering and CLAUDE.md update

**Files:**
- Modify: `src/debussy/board.py` (line 155-157: `cmd_board`)
- Modify: `src/debussy/__main__.py` (line 47-48: board subparser)
- Modify: `CLAUDE.md`

- [ ] **Step 1: Add `-p` argument to board subparser**

In `src/debussy/__main__.py`, update the board parser (around line 47):

```python
p = subparsers.add_parser("board", help="Show kanban board")
p.add_argument("-p", "--project", help="Filter by project prefix")
p.set_defaults(func=cmd_board)
```

- [ ] **Step 2: Update `cmd_board` to pass prefix**

In `src/debussy/board.py`, update `cmd_board`:

```python
def cmd_board(args):
    prefix = getattr(args, "project", None)
    with get_db() as db:
        all_tasks = list_tasks(db, prefix=prefix)
    running = get_running_agents()
    all_tasks_by_id = {t.get("id"): t for t in all_tasks if t.get("id")}

    buckets = _build_buckets(all_tasks, running, all_tasks_by_id)
    term_width = shutil.get_terminal_size().columns

    print(_render_vertical(BOARD_COLUMNS, buckets, running, all_tasks_by_id, term_width))

    print()
    print_runtime_info(running)
```

- [ ] **Step 3: Update CLAUDE.md commands section**

Add to the Commands section in `CLAUDE.md`:

```
takt project add <PREFIX> <NAME> [--default]  # Add a project
takt project list                              # List projects
takt project default [PREFIX]                  # Show or switch default
takt project rm <PREFIX>                       # Remove a project
```

Update `takt create` line to show `-p` flag:

```
takt create "title" [-p PREFIX] -d "description"
```

Update `takt list` line:

```
takt list [-p PREFIX]
```

Remove or update the `takt prefix` line to note deprecation.

- [ ] **Step 4: Run full test suite**

Run: `python -m pytest tests/ -v`
Expected: ALL PASS

- [ ] **Step 5: Commit**

```bash
git add src/debussy/board.py src/debussy/__main__.py CLAUDE.md
git commit -m "[takt] Add -p filter to board, update CLAUDE.md with project commands"
```
