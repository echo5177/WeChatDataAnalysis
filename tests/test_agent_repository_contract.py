import json
import sys
import tomllib
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))


class TestAgentRepositoryContract(unittest.TestCase):
    def test_agent_instruction_and_skill_files_are_present(self):
        self.assertTrue((ROOT / "AGENTS.md").is_file())
        self.assertEqual((ROOT / "CLAUDE.md").read_text(encoding="utf-8").strip(), "@AGENTS.md")
        skill = (ROOT / ".agents" / "skills" / "wechat-data-operator" / "SKILL.md").read_text(encoding="utf-8")
        self.assertIn("name: wechat-data-operator", skill)
        self.assertNotIn("[TODO", skill)

    def test_codex_and_claude_launch_the_same_stdio_server(self):
        codex = tomllib.loads((ROOT / ".codex" / "config.toml").read_text(encoding="utf-8"))
        claude = json.loads((ROOT / ".mcp.json").read_text(encoding="utf-8"))
        codex_server = codex["mcp_servers"]["wechat_data_analysis"]
        claude_server = claude["mcpServers"]["wechat-data-analysis"]
        self.assertEqual(codex_server["command"], "uv")
        self.assertEqual(codex_server["args"], claude_server["args"])
        self.assertEqual(codex_server["args"][-2:], ["mcp", "stdio"])


if __name__ == "__main__":
    unittest.main()
