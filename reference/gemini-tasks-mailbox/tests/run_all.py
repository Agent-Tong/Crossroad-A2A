"""One sequential run of both test modules. Usage: /usr/bin/python3 -I -B tests/run_all.py"""
import pathlib
import sys
import unittest

HERE = pathlib.Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(HERE.parent))

if __name__ == "__main__":
    import test_gemini_p2
    import test_review_fixes
    suite = unittest.TestSuite()
    loader = unittest.defaultTestLoader
    suite.addTests(loader.loadTestsFromModule(test_gemini_p2))
    suite.addTests(loader.loadTestsFromModule(test_review_fixes))
    result = unittest.TextTestRunner(verbosity=2).run(suite)
    raise SystemExit(0 if result.wasSuccessful() else 1)
