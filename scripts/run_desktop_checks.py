"""Run desktop validation with Tk finalization on the owning thread.

Python 3.14 may trigger cyclic garbage collection on a database worker. Test
roots must instead release their widget/Variable cycles on their Tk thread.
"""
import gc
import sys
import unittest

DEFAULT_MODULES = [
    'tests.test_ui_smoke', 'tests.test_ui_refinement', 'tests.test_ui_ministry',
    'tests.test_ui_leadership', 'tests.test_ui_administration',
    'tests.test_ui_household', 'tests.test_ui_sunday_school',
]


def main():
    was_enabled=gc.isenabled();gc.disable()
    from tests import test_ui_smoke
    original=test_ui_smoke.UiSmokeTests.tearDown
    def owner_teardown(self):
        original(self)
        gc.collect()
    test_ui_smoke.UiSmokeTests.tearDown=owner_teardown
    try:
        suite=unittest.TestLoader().loadTestsFromNames(sys.argv[1:] or DEFAULT_MODULES)
        result=unittest.TextTestRunner(verbosity=2).run(suite)
        gc.collect()
        return 0 if result.wasSuccessful() else 1
    finally:
        test_ui_smoke.UiSmokeTests.tearDown=original
        if was_enabled:gc.enable()


if __name__=='__main__':raise SystemExit(main())
