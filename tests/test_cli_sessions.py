from unittest.mock import patch, MagicMock

from debussy.cli import cmd_sessions


class TestCmdSessions:
    @patch("debussy.cli.list_debussy_sessions")
    def test_prints_sessions(self, mock_list, capsys):
        mock_list.return_value = [
            {"session": "debussy-piklr", "path": "/root/projects/piklr"},
            {"session": "debussy-myapp", "path": "/root/projects/myapp"},
        ]

        cmd_sessions(MagicMock())

        output = capsys.readouterr().out
        assert "debussy-piklr" in output
        assert "/root/projects/piklr" in output
        assert "debussy-myapp" in output

    @patch("debussy.cli.list_debussy_sessions")
    def test_prints_no_sessions(self, mock_list, capsys):
        mock_list.return_value = []

        cmd_sessions(MagicMock())

        output = capsys.readouterr().out
        assert "No active sessions" in output
