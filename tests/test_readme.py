import os
import re
import unittest

from src.encode import ROOT

README = os.path.join(ROOT, "README.md")

# (what the section is, regex its heading must match)
SECTIONS = [
    ("what it is / interpretation of Speed", r"what it is|interpretation"),
    ("physics", r"physics"),
    ("how to run", r"how to run"),
    ("workflow notes", r"workflow"),
    ("asset and AI disclosure", r"disclosure"),
    ("how it was rendered", r"how it was rendered"),
]


def text():
    with open(README, encoding="utf-8") as fh:
        return fh.read()


def section(name_re):
    """Body of the first '## ' section whose heading matches name_re."""
    parts = re.split(r"^## (.*)$", text(), flags=re.M)
    for head, body in zip(parts[1::2], parts[2::2]):
        if re.search(name_re, head, re.I):
            return body
    return None


class ReadmeTest(unittest.TestCase):
    def test_required_sections_exist_and_are_not_empty(self):
        for label, rx in SECTIONS:
            body = section(rx)
            self.assertIsNotNone(body, "missing section: " + label)
            self.assertGreater(len((body or "").strip()), 80, "section too thin: " + label)

    def test_physics_has_the_equations(self):
        body = section(r"physics") or ""
        for needle in ("γ", "cos θ'", "D = γ(1 + β cos θ", "D⁴", "min(D²", "C = 120", "smoothstep"):
            self.assertIn(needle, body)

    def test_how_to_run_lists_every_command(self):
        body = section(r"how to run") or ""
        for cmd in ("bun run test", "bun run smoke", "bun run preview", "bun run render",
                    "bun run render:status", "bun run encode", "bun run media", "BLENDER", "FFMPEG"):
            self.assertIn(cmd, body)

    def test_rendered_section_tells_the_truth(self):
        body = section(r"how it was rendered") or ""
        for needle in ("RTX 3090", "1920x1080", "360", "48 samples", "not rendered on the RenderJuice"):
            self.assertIn(needle, body)
        self.assertNotIn("Cloud REST API", text())

    def test_disclosure_names_font_and_ai(self):
        body = section(r"disclosure") or ""
        for needle in ("no third-party", "Blender's bundled font", "AI coding assistant", "No AI-generated"):
            self.assertIn(needle, body)

    def test_every_relative_link_and_image_exists(self):
        links = re.findall(r"!?\[[^\]]*\]\(([^)\s]+)\)", text())
        self.assertGreater(len(links), 5)
        local = [l for l in links if not re.match(r"[a-z]+:|#", l)]
        missing = [l for l in local if not os.path.exists(os.path.join(ROOT, l.split("#")[0]))]
        self.assertEqual(missing, [], "README links to missing files")
