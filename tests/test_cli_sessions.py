from unittest.mock import patch, MagicMock

from debussy.cli import cmd_connect, cmd_sessions


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


class TestCmdConnect:
    @patch("debussy.cli.os.execvp")
    @patch("debussy.cli.os.chdir")
    @patch("debussy.cli.list_debussy_sessions")
    def test_connect_by_name(self, mock_list, mock_chdir, mock_exec):
        mock_list.return_value = [
            {"session": "debussy-piklr", "path": "/root/projects/piklr"},
        ]
        args = MagicMock()
        args.name = "piklr"

        cmd_connect(args)

        mock_chdir.assert_called_once_with("/root/projects/piklr")
        mock_exec.assert_called_once_with(
            "tmux", ["tmux", "attach-session", "-t", "debussy-piklr"]
        )

    @patch("debussy.cli.os.execvp")
    @patch("debussy.cli.os.chdir")
    @patch("debussy.cli.list_debussy_sessions")
    def test_connect_auto_single_session(self, mock_list, mock_chdir, mock_exec):
        mock_list.return_value = [
            {"session": "debussy-piklr", "path": "/root/projects/piklr"},
        ]
        args = MagicMock()
        args.name = None

        cmd_connect(args)

        mock_chdir.assert_called_once_with("/root/projects/piklr")
        mock_exec.assert_called_once()

    @patch("debussy.cli.list_debussy_sessions")
    def test_connect_no_sessions(self, mock_list, capsys):
        mock_list.return_value = []
        args = MagicMock()
        args.name = "piklr"

        result = cmd_connect(args)

        assert result == 1
        assert "No active sessions" in capsys.readouterr().out

    @patch("debussy.cli.list_debussy_sessions")
    def test_connect_multiple_no_name(self, mock_list, capsys):
        mock_list.return_value = [
            {"session": "debussy-piklr", "path": "/root/projects/piklr"},
            {"session": "debussy-myapp", "path": "/root/projects/myapp"},
        ]
        args = MagicMock()
        args.name = None

        result = cmd_connect(args)

        assert result == 1
        output = capsys.readouterr().out
        assert "debussy-piklr" in output

    @patch("debussy.cli.list_debussy_sessions")
    def test_connect_name_not_found(self, mock_list, capsys):
        mock_list.return_value = [
            {"session": "debussy-piklr", "path": "/root/projects/piklr"},
        ]
        args = MagicMock()
        args.name = "notfound"

        result = cmd_connect(args)

        assert result == 1
        assert "not found" in capsys.readouterr().out
