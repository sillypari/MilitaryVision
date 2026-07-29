from __future__ import annotations

import sys
import traceback

from PySide6.QtWidgets import QApplication, QMessageBox

from persistent_tracker.config import load_config, project_root
from persistent_tracker.ui.main_window import MainWindow
from persistent_tracker.ui.styles import APP_STYLESHEET
from persistent_tracker.utils.logging import configure_logging


def main() -> int:
    config = load_config()
    configure_logging(project_root() / "output" / "logs", config.application.debug)

    application = QApplication(sys.argv)
    application.setApplicationName(config.application.name)
    application.setStyle("Fusion")
    application.setStyleSheet(APP_STYLESHEET)

    def handle_exception(
        exception_type: type[BaseException],
        exception: BaseException,
        exception_traceback: object,
    ) -> None:
        traceback.print_exception(exception_type, exception, exception_traceback)
        QMessageBox.critical(
            None,
            "Unexpected error",
            f"{exception}\n\nDetails were written to the application log.",
        )

    sys.excepthook = handle_exception
    window = MainWindow(config)
    window.show()
    return application.exec()


if __name__ == "__main__":
    raise SystemExit(main())
