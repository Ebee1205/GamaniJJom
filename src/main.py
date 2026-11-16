"""
Copyright (c) 2025. Ebee1205(wavicle) all rights reserved.

The copyright of this software belongs to Ebee1205(wavicle).
All rights reserved.
"""

import argparse
import os
import signal
import sys
import traceback
from enum import IntEnum
from pathlib import Path

# python src/main.py 와 python -m src.main 실행 방식을 모두 지원한다.
PROJECT_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_CONFIG_PATH = PROJECT_ROOT / "src" / "config" / "gamani-jjom.cfg.json"
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))


class ExitCode(IntEnum):
    OK = 0
    FAILURE = 1
    INTERRUPTED = 130


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="GamaniJJom Windows utility")
    parser.add_argument(
        "--check",
        action="store_true",
        help="Check configuration, logger and imports without opening the GUI",
    )
    parser.add_argument(
        "--cfg",
        type=Path,
        default=Path(os.environ.get("GAMANI_CONFIG", DEFAULT_CONFIG_PATH)),
        help="Path to cfg JSON (default: src/config/gamani-jjom.cfg.json, "
        "or env GAMANI_CONFIG)",
    )
    parser.add_argument("--smoke-test", action="store_true",
                        help="Open Qt picker/tray and quit after 1.2 seconds")
    args = parser.parse_args(argv)

    if sys.platform != "win32":
        parser.exit(ExitCode.FAILURE, "GamaniJJom requires Windows.\n")
    return args


def initialize_context(config_path: Path):
    """설정을 불러오고 애플리케이션 로거를 초기화한다."""
    from src.app_context import AppContext

    ctx = AppContext()
    cfg = ctx.load_config(str(config_path))

    log_path = Path(cfg.logger.path).expanduser()

    if not log_path.is_absolute():
        log_path = PROJECT_ROOT / log_path

    # logger 초기화
    cfg.logger.path = str(log_path)
    ctx._init_logger()
    return ctx


def run_log_selftest(log) -> None:
    """로깅 테스트 (--check 에서만 실행)"""
    log.info("APP", "-- LOG TEST START --")
    log.debug("APP", "test debug level")
    log.info("APP", "test info level")
    log.warning("APP", "test warn level")
    log.error("APP", "test error level")
    log.info("APP", "-- LOG TEST END --")


def run(ctx, args: argparse.Namespace) -> ExitCode:
    cfg = ctx.cfg
    ctx.log.info(
        "APP",
        f"Initializing {cfg.project_name} (env={cfg.environment}, cfg={args.cfg})",
    )

    from PySide6.QtCore import QTimer
    from PySide6.QtWidgets import QApplication
    from src.ui.application import DesktopController

    if args.check:
        run_log_selftest(ctx.log)
        print("Configuration, logger, PySide6 and Win32 imports OK (GUI not tested).")
        return ExitCode.OK

    from src.adapters.windows.window_api import enable_dpi_awareness

    enable_dpi_awareness()
    app = QApplication([sys.argv[0]])
    app.setApplicationName("GamaniJJom")
    app.setQuitOnLastWindowClosed(False)
    from src.ui.resources import apply_theme
    apply_theme(app)

    callback_failed = False

    def report_exception(exc_type, exc_value, exc_tb):
        nonlocal callback_failed
        callback_failed = True
        ctx.log.error("UI", "Unhandled Qt callback exception",
                      exc_info=(exc_type, exc_value, exc_tb))

    previous_hook = sys.excepthook
    sys.excepthook = report_exception
    controller = DesktopController(app, ctx)
    try:
        if not controller.start():
            return ExitCode.FAILURE
        
        def handle_signal(signum, frame):
            ctx.log.info("APP", f"Received signal {signum}, shutting down...")
            app.quit()
        
        signal.signal(signal.SIGINT, handle_signal)
        signal.signal(signal.SIGTERM, handle_signal)
        
        if args.smoke_test:
            QTimer.singleShot(1200, app.quit)
        ctx.log.info("APP", "Qt application started")
        result = app.exec()
        return ExitCode.OK if result == 0 and not callback_failed else ExitCode.FAILURE
    finally:
        controller.shutdown()
        sys.excepthook = previous_hook


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)

    try:
        ctx = initialize_context(args.cfg)
    except Exception:
        # 설정/임포트/로거 초기화는 로거가 만들어지기 전에 실패할 수 있다.
        traceback.print_exc()
        return ExitCode.FAILURE

    try:
        return run(ctx, args)
    except KeyboardInterrupt:
        ctx.log.info("APP", "Interrupted by user")
        return ExitCode.INTERRUPTED
    except Exception:
        ctx.log.error("APP", "Application failed", exc_info=True)
        return ExitCode.FAILURE
    finally:
        ctx.shutdown()


if __name__ == "__main__":
    raise SystemExit(main())
