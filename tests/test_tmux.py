from unittest.mock import patch, MagicMock

from debussy.tmux import list_debussy_sessions


class TestListDebussySessions:
    @patch("debussy.tmux.subprocess.run")
    def test_returns_sessions_with_paths(self, mock_run):
        mock_run.side_effect = [
            MagicMock(returncode=0, stdout="debussy-piklr\ndebussy-myapp\nother-session\n"),
            MagicMock(returncode=0, stdout="/root/projects/piklr\n"),
            MagicMock(returncode=0, stdout="/root/projects/myapp\n"),
        ]

        result = list_debussy_sessions()

        assert result == [
            {"session": "debussy-piklr", "path": "/root/projects/piklr"},
            {"session": "debussy-myapp", "path": "/root/projects/myapp"},
        ]

    @patch("debussy.tmux.subprocess.run")
    def test_returns_empty_when_no_tmux(self, mock_run):
        mock_run.return_value = MagicMock(returncode=1, stdout="")

        result = list_debussy_sessions()

        assert result == []

    @patch("debussy.tmux.subprocess.run")
    def test_returns_empty_when_no_debussy_sessions(self, mock_run):
        mock_run.return_value = MagicMock(returncode=0, stdout="other-session\n")

        result = list_debussy_sessions()

        assert result == []

    @patch("debussy.tmux.subprocess.run")
    def test_returns_unknown_path_on_display_failure(self, mock_run):
        mock_run.side_effect = [
            MagicMock(returncode=0, stdout="debussy-broken\n"),
            MagicMock(returncode=1, stdout=""),
        ]

        result = list_debussy_sessions()

        assert result == [{"session": "debussy-broken", "path": "unknown"}]
