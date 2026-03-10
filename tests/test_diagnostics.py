import tempfile
from pathlib import Path

from debussy.diagnostics import read_log_tail, format_death_comment


class TestReadLogTail:
    def test_reads_last_n_lines(self):
        with tempfile.NamedTemporaryFile(mode="w", suffix=".log", delete=False) as f:
            for i in range(20):
                f.write(f"line {i}\n")
            f.flush()
            result = read_log_tail(f.name, max_lines=5)
            assert "line 19" in result
            assert "line 15" in result
            assert "line 14" not in result

    def test_returns_empty_for_missing_file(self):
        result = read_log_tail("/nonexistent/path.log")
        assert result == ""

    def test_returns_full_content_when_short(self):
        with tempfile.NamedTemporaryFile(mode="w", suffix=".log", delete=False) as f:
            f.write("only line\n")
            f.flush()
            result = read_log_tail(f.name, max_lines=10)
            assert "only line" in result

    def test_truncates_long_lines(self):
        with tempfile.NamedTemporaryFile(mode="w", suffix=".log", delete=False) as f:
            f.write("x" * 500 + "\n")
            f.flush()
            result = read_log_tail(f.name, max_lines=5, max_line_len=100)
            assert len(result.splitlines()[0]) <= 103  # 100 + "..."


class TestFormatDeathComment:
    def test_includes_agent_name_and_elapsed(self):
        result = format_death_comment("developer-bach", 5, "open", "error on line 1\ncrash")
        assert "developer-bach" in result
        assert "5s" in result

    def test_includes_log_tail(self):
        result = format_death_comment("developer-bach", 5, "open", "some error output")
        assert "some error output" in result

    def test_handles_empty_log(self):
        result = format_death_comment("developer-bach", 5, "open", "")
        assert "developer-bach" in result
        assert "no log" in result.lower()
