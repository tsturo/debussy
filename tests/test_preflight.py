import subprocess
from unittest.mock import MagicMock, patch

from debussy.preflight import check_base_branch, check_remote_ref


class TestCheckBaseBranch:
    def test_returns_none_when_base_branch_set_and_exists(self):
        with patch("debussy.preflight.get_config", return_value={"base_branch": "feature/foo"}):
            with patch("debussy.preflight.subprocess.run") as mock_run:
                mock_run.return_value = MagicMock(returncode=0)
                assert check_base_branch() is None

    def test_returns_error_when_base_branch_not_set(self):
        with patch("debussy.preflight.get_config", return_value={}):
            result = check_base_branch()
            assert result is not None
            assert "not configured" in result

    def test_returns_error_when_remote_ref_missing(self):
        with patch("debussy.preflight.get_config", return_value={"base_branch": "feature/foo"}):
            with patch("debussy.preflight.subprocess.run") as mock_run:
                mock_run.return_value = MagicMock(returncode=128)
                result = check_base_branch()
                assert result is not None
                assert "not found" in result


class TestCheckRemoteRef:
    def test_returns_none_when_ref_exists(self):
        with patch("debussy.preflight.subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(returncode=0)
            assert check_remote_ref("origin/feature/bd-001") is None

    def test_returns_error_when_ref_missing(self):
        with patch("debussy.preflight.subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(returncode=128)
            result = check_remote_ref("origin/feature/bd-001")
            assert result is not None
            assert "bd-001" in result


class TestPreflightSpawn:
    def test_developer_checks_base_branch(self):
        with patch("debussy.preflight.check_base_branch", return_value="base_branch not configured") as mock:
            from debussy.preflight import preflight_spawn
            result = preflight_spawn("developer", "bd-001")
            assert result is not None
            mock.assert_called_once()

    def test_reviewer_checks_feature_branch(self):
        with patch("debussy.preflight.check_base_branch", return_value=None):
            with patch("debussy.preflight.check_remote_ref", return_value="ref not found") as mock:
                from debussy.preflight import preflight_spawn
                result = preflight_spawn("reviewer", "bd-001")
                assert result is not None
                mock.assert_called_once_with("origin/feature/bd-001")

    def test_investigator_only_checks_base_branch(self):
        with patch("debussy.preflight.check_base_branch", return_value=None):
            with patch("debussy.preflight.check_remote_ref") as mock:
                from debussy.preflight import preflight_spawn
                result = preflight_spawn("investigator", "bd-001")
                assert result is None
                mock.assert_not_called()

    def test_developer_passes_all_checks(self):
        with patch("debussy.preflight.check_base_branch", return_value=None):
            from debussy.preflight import preflight_spawn
            result = preflight_spawn("developer", "bd-001")
            assert result is None

    def test_integrator_checks_base_branch(self):
        with patch("debussy.preflight.check_base_branch", return_value=None):
            from debussy.preflight import preflight_spawn
            result = preflight_spawn("integrator", "bd-001")
            assert result is None
