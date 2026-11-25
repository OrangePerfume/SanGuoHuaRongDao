"""Run the complete unittest suite with an explicit Qt application lifetime.

The GUI tests must run on CI. A unittest "OK" line alone is not enough: the
process exit status (including Qt teardown) is part of the quality gate.
"""
from __future__ import annotations

import argparse
import gc
import importlib.util
import os
from pathlib import Path
import sys
import traceback
import unittest

PROJECT = Path(__file__).resolve().parents[1]
if str(PROJECT) not in sys.path:
    sys.path.insert(0, str(PROJECT))


def _close_qt(app: object) -> None:
    """Dispose of widgets and QApplication while Qt modules are fully alive."""
    from PySide6.QtCore import QCoreApplication, QEvent
    from PySide6.QtWidgets import QApplication
    from shiboken6 import delete, isValid

    if not isValid(app):
        raise RuntimeError("QApplication was destroyed before test teardown")

    # No Qt window should survive past the test process; deferred deletes must
    # be processed before QApplication itself is destroyed.
    for widget in QApplication.topLevelWidgets():
        widget.close()
        widget.deleteLater()
    QCoreApplication.sendPostedEvents(None, QEvent.Type.DeferredDelete)
    app.processEvents()

    # unittest test classes retain an app reference from setUpClass. Release
    # those references before deleting the C++ QApplication instance.
    for module_name, module in tuple(sys.modules.items()):
        if not module_name.startswith('test_') or module is None:
            continue
        for member in vars(module).values():
            if (isinstance(member, type)
                    and issubclass(member, unittest.TestCase)
                    and member.__dict__.get("app") is app):
                delattr(member, "app")
    gc.collect()

    if QApplication.topLevelWidgets():
        raise RuntimeError("Qt test windows remain alive after cleanup")
    delete(app)
    if QApplication.instance() is not None:
        raise RuntimeError("QApplication still exists after explicit teardown")


def gate_failure(result: unittest.TestResult | None, require_qt: bool,
                 errors: list[str]) -> str | None:
    """No success result, an uncaught Qt error, or skipped strict tests is fatal."""
    if result is None or not result.wasSuccessful():
        return "unit tests did not pass"
    if errors:
        return "unhandled Qt callback error or Qt teardown failure"
    if require_qt and result.skipped:
        return f"{len(result.skipped)} test(s) skipped in strict mode"
    return None


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--require-qt", action="store_true",
        help="Fail rather than skip GUI tests when PySide6 is missing",
    )
    args = parser.parse_args(argv)
    os.chdir(PROJECT)

    errors: list[str] = []
    initial_excepthook = sys.excepthook

    def qt_exception_hook(exc_type, value, tb) -> None:
        message = "".join(traceback.format_exception(exc_type, value, tb))
        errors.append(message)
        initial_excepthook(exc_type, value, tb)

    sys.excepthook = qt_exception_hook
    qt_app = None
    result: unittest.TestResult | None = None
    try:
        if importlib.util.find_spec("PySide6"):
            from PySide6.QtWidgets import QApplication
            qt_app = QApplication.instance() or QApplication([])
            qt_app.setQuitOnLastWindowClosed(False)
        elif args.require_qt:
            print("ERROR: PySide6 unavailable; GUI tests must not be skipped", file=sys.stderr)
            return 1

        suite = unittest.defaultTestLoader.discover(
            start_dir=str(PROJECT / "tests"), pattern="test_*.py"
        )
        result = unittest.TextTestRunner(verbosity=2).run(suite)
        print(
            f"UNITTEST: success={result.wasSuccessful()} "
            f"executed={result.testsRun} skipped={len(result.skipped)}",
            flush=True,
        )
    except BaseException:
        errors.append(traceback.format_exc())
        print(errors[-1], file=sys.stderr, flush=True)
    finally:
        if qt_app is not None:
            try:
                _close_qt(qt_app)
                print("QT_CLEANUP: completed", flush=True)
            except BaseException:
                errors.append(traceback.format_exc())
                print("QT_CLEANUP: ERROR\n" + errors[-1], file=sys.stderr, flush=True)
        sys.excepthook = initial_excepthook

    failure = gate_failure(result, args.require_qt, errors)
    if failure:
        print(f"CI_TEST_GATE: FAILED; {failure}", file=sys.stderr, flush=True)
        return 1
    mode = "Qt tests and shutdown" if qt_app is not None else "non-Qt tests only"
    print(f"CI_TEST_GATE: PASSED ({mode})", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
