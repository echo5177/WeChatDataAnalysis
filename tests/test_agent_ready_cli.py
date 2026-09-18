import sys
import unittest
from contextlib import redirect_stderr, redirect_stdout
from io import StringIO
import json
from pathlib import Path
from unittest.mock import patch


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))


from wechat_decrypt_tool import cli


class TestAgentReadyCli(unittest.TestCase):
    def test_status_routes_agent_to_data_preparation_when_empty(self):
        with patch.object(cli, "_live_accounts", return_value=[]), patch.object(cli, "_archive_accounts", return_value=[]):
            payload = cli.build_status()

        self.assertEqual(payload["status"], "needs_user_action")
        self.assertEqual(payload["nextAction"]["code"], "prepare_data")
        self.assertIn("wechat-archive start", payload["nextAction"]["command"])

    def test_static_archive_is_enough_for_ready_status(self):
        archive = [{"account": "archive-only", "conversationCount": 1, "messageCount": 2}]
        with patch.object(cli, "_live_accounts", return_value=[]), patch.object(cli, "_archive_accounts", return_value=archive):
            payload = cli.build_status()

        self.assertEqual(payload["status"], "ready")
        self.assertFalse(payload["liveReady"])
        self.assertTrue(payload["archiveReady"])

    def test_json_mode_reserves_stdout_for_one_parseable_document(self):
        payload = {"status": "ready", "nextAction": None}

        def noisy_status():
            print("application log")
            return payload

        stdout = StringIO()
        stderr = StringIO()
        with patch.object(cli, "build_status", side_effect=noisy_status), redirect_stdout(stdout), redirect_stderr(stderr):
            exit_code = cli.main(["status", "--json"])

        self.assertEqual(exit_code, 0)
        self.assertEqual(json.loads(stdout.getvalue()), payload)
        self.assertIn("application log", stderr.getvalue())


if __name__ == "__main__":
    unittest.main()
