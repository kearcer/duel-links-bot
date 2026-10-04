from pathlib import Path
import re
import unittest


ROOT = Path(__file__).resolve().parents[1]


class RepositoryContractTests(unittest.TestCase):
    def test_tool_dependencies_match_ci(self) -> None:
        requirements = (ROOT / "tools" / "requirements.txt").read_text("utf-8")
        self.assertIn("jsonschema==4.26.0", requirements)
        self.assertIn("referencing==0.37.0", requirements)
        self.assertIn("Pillow>=10.4.0,<13", requirements)

    def test_agent_runtime_matches_ci_framework_version(self) -> None:
        requirements = (ROOT / "agent" / "requirements.txt").read_text("utf-8")
        workflow = (ROOT / ".github" / "workflows" / "install.yml").read_text(
            "utf-8"
        )
        match = re.search(r'MAAFW_VERSION:\s*"v(?P<version>[0-9.]+)"', workflow)
        self.assertIsNotNone(match)
        self.assertEqual(requirements.strip(), f"maafw=={match.group('version')}")

    def test_local_runtime_outputs_are_ignored(self) -> None:
        ignore = (ROOT / ".gitignore").read_text("utf-8")
        self.assertIn(".venv/", ignore)
        self.assertIn(".tmp/", ignore)
        self.assertIn("tests/artifacts/", ignore)
