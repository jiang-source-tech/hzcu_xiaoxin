import os
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

os.environ.setdefault("DEEPSEEK_API_KEY", "test-key")
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import app as app_module


class RunToolEncodingTest(unittest.TestCase):
    def test_decodes_non_utf8_tool_stdout_without_subprocess_text_mode(self):
        class FakeResult:
            stdout = "工具输出".encode("gbk")
            stderr = b""

        with tempfile.TemporaryDirectory() as tmp:
            skill_dir = Path(tmp)
            (skill_dir / "tools").mkdir()
            (skill_dir / "tools" / "memory_manager.py").write_text("", encoding="utf-8")

            with patch.object(app_module, "SKILL_DIR", skill_dir), \
                 patch.object(app_module, "DATA_DIR", skill_dir / "data"), \
                 patch.object(app_module.subprocess, "run", return_value=FakeResult()) as run:
                output = app_module.run_tool("memory_load", "alice")

        self.assertEqual(output, "工具输出")
        self.assertNotIn("text", run.call_args.kwargs)
        self.assertNotIn("encoding", run.call_args.kwargs)


if __name__ == "__main__":
    unittest.main()
