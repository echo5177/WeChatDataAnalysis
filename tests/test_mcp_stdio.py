import asyncio
import io
import json
import sys
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))


from wechat_decrypt_tool.mcp.stdio import serve_stdio


class TestMcpStdio(unittest.TestCase):
    def test_newline_jsonrpc_transport(self):
        requests = [
            {"jsonrpc": "2.0", "id": 1, "method": "initialize"},
            {"jsonrpc": "2.0", "method": "notifications/initialized"},
            {"jsonrpc": "2.0", "id": 2, "method": "tools/list", "params": {"limit": 2}},
            {"jsonrpc": "2.0", "id": 3, "method": "ping"},
        ]
        source = io.BytesIO(b"".join(json.dumps(item).encode("utf-8") + b"\n" for item in requests))
        sink = io.BytesIO()

        asyncio.run(serve_stdio(source, sink))

        responses = [json.loads(line) for line in sink.getvalue().splitlines()]
        self.assertEqual([item["id"] for item in responses], [1, 2, 3])
        self.assertEqual(responses[0]["result"]["serverInfo"]["name"], "wechat-data-analysis-mcp")
        self.assertEqual(responses[1]["result"]["count"], 2)
        self.assertEqual(responses[2]["result"], {})

    def test_parse_error_is_returned_without_stopping_server(self):
        source = io.BytesIO(b"{bad json\n" + b'{"jsonrpc":"2.0","id":9,"method":"ping"}\n')
        sink = io.BytesIO()

        asyncio.run(serve_stdio(source, sink))

        responses = [json.loads(line) for line in sink.getvalue().splitlines()]
        self.assertEqual(responses[0]["error"]["code"], -32700)
        self.assertEqual(responses[1], {"jsonrpc": "2.0", "id": 9, "result": {}})


if __name__ == "__main__":
    unittest.main()
