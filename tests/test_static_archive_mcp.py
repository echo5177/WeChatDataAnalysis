import os
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from fastapi import FastAPI
from fastapi.testclient import TestClient


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))


class TestStaticArchiveMcp(unittest.TestCase):
    TOKEN = "static-archive-test-token-123456"

    def setUp(self):
        self.output = tempfile.TemporaryDirectory()
        self.old_output = os.environ.get("WECHAT_TOOL_OUTPUT_DIR")
        self.old_token = os.environ.get("WECHAT_TOOL_MCP_TOKEN")
        os.environ["WECHAT_TOOL_OUTPUT_DIR"] = self.output.name
        os.environ["WECHAT_TOOL_MCP_TOKEN"] = self.TOKEN

        from wechat_decrypt_tool import static_archive_store as store

        self.store = store
        store.upsert_conversation("archive-only", "group@chatroom", name="Test Group", is_group=True)
        store.upsert_messages(
            "archive-only",
            "group@chatroom",
            [
                {
                    "serverIdStr": "1001",
                    "localId": 1,
                    "createTime": 100,
                    "senderUsername": "alice",
                    "senderDisplayName": "Alice",
                    "content": "第一条归档消息",
                    "type": 1,
                },
                {
                    "serverIdStr": "1002",
                    "localId": 2,
                    "createTime": 200,
                    "senderUsername": "bob",
                    "senderDisplayName": "Bob",
                    "content": "第二条归档消息",
                    "type": 1,
                },
            ],
        )

    def tearDown(self):
        if self.old_output is None:
            os.environ.pop("WECHAT_TOOL_OUTPUT_DIR", None)
        else:
            os.environ["WECHAT_TOOL_OUTPUT_DIR"] = self.old_output
        if self.old_token is None:
            os.environ.pop("WECHAT_TOOL_MCP_TOKEN", None)
        else:
            os.environ["WECHAT_TOOL_MCP_TOKEN"] = self.old_token
        self.output.cleanup()

    def _client(self):
        from wechat_decrypt_tool.routers.mcp import router

        app = FastAPI()
        app.include_router(router)
        client = TestClient(app)
        client.headers.update({"Authorization": f"Bearer {self.TOKEN}"})
        return client

    @staticmethod
    def _rpc(name, arguments=None, request_id=1):
        return {
            "jsonrpc": "2.0",
            "id": request_id,
            "method": "tools/call",
            "params": {"name": name, "arguments": arguments or {}},
        }

    def test_archive_account_is_discovered_without_live_database(self):
        accounts = self.store.list_accounts()
        self.assertEqual(accounts[0]["account"], "archive-only")
        self.assertEqual(accounts[0]["messageCount"], 2)

        with patch("wechat_decrypt_tool.mcp.tools._list_decrypted_accounts", return_value=[]):
            response = self._client().post("/mcp", json=self._rpc("wechat.core.get_status"))

        result = response.json()["result"]["structuredContent"]
        self.assertFalse(result["dbReady"])
        self.assertTrue(result["archiveReady"])
        self.assertEqual(result["defaultAccount"], "archive-only")

    def test_static_tools_default_to_archive_account_and_keep_reads_bounded(self):
        client = self._client()
        with patch("wechat_decrypt_tool.mcp.tools._list_decrypted_accounts", return_value=[]):
            conversations = client.post(
                "/mcp", json=self._rpc("wechat.static.list_conversations")
            ).json()["result"]["structuredContent"]
            messages = client.post(
                "/mcp",
                json=self._rpc(
                    "wechat.static.read_range",
                    {"username": "group@chatroom", "limit": 0},
                    request_id=2,
                ),
            ).json()["result"]["structuredContent"]

        self.assertEqual(conversations["account"], "archive-only")
        self.assertEqual(conversations["count"], 1)
        self.assertEqual(messages["account"], "archive-only")
        self.assertEqual(messages["count"], 1)
        self.assertEqual(messages["messages"][0]["text"], "第二条归档消息")


if __name__ == "__main__":
    unittest.main()
