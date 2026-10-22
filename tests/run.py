"""Run the unittest suite inside headless Blender. Exits 1 on any failure."""
import os
import sys
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

pattern = sys.argv[sys.argv.index("--") + 1] if "--" in sys.argv else "test*.py"  # bun run test:only -- test_look.py
suite = unittest.defaultTestLoader.discover(
    os.path.join(ROOT, "tests"), pattern=pattern, top_level_dir=ROOT
)
result = unittest.TextTestRunner(verbosity=2).run(suite)
sys.exit(0 if result.wasSuccessful() else 1)
