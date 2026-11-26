"""
Copyright (c) 2025. Ebee1205(wavicle) all rights reserved.

The copyright of this software belongs to Ebee1205(wavicle).
All rights reserved.
"""

import argparse
import os
import signal
import subprocess
import sys
import traceback
from enum import IntEnum
from pathlib import Path

# python src/main.py 와 python -m src.main 실행 방식을 모두 지원한다.
PROJECT_ROOT = Path(getattr(sys, "_MEIPASS", Path(__file__).resolve().parent.parent))
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.runtime_paths import data_root, default_config_path, is_frozen, prepare_default_config

DEFAULT_CONFIG_PATH = default_config_path()


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
    parser.add_argument("--build", action="store_true",
                        help="Build and verify the Windows EXE (source only)")
    args = parser.parse_args(argv)

    if sys.platform != "win32":
        parser.exit(ExitCode.FAILURE, "GamaniJJom requires Windows.\n")
    if args.build:
        if is_frozen():
            parser.error("--build is only available from the source checkout")
        if args.check or args.smoke_test:
            parser.error("--build cannot be combined with --check or --smoke-test")
    return args


def build_exe() -> int:
    script = PROJECT_ROOT / "packaging" / "build-exe.ps1"
    if not script.is_file():
        print(f"Build script not found: {script}", file=sys.stderr)
        return ExitCode.FAILURE

    try:
        result = subprocess.run(
            ["powershell.exe", "-NoProfile", "-ExecutionPolicy", "RemoteSigned",
             "-File", str(script), "-Python", sys.executable],
            cwd=PROJECT_ROOT,
        )
        return result.returncode
    except KeyboardInterrupt:
        return ExitCode.INTERRUPTED
    except OSError as exc:
        print(f"Could not start the build: {exc}", file=sys.stderr)
        return ExitCode.FAILURE


def initialize_context(config_path: Path):
    """설정을 불러오고 애플리케이션 로거를 초기화한다."""
    from src.app_context import AppContext

    if is_frozen() and config_path.resolve() == DEFAULT_CONFIG_PATH.resolve():
        prepare_default_config()
    ctx = AppContext()
    cfg = ctx.load_config(str(config_path))

    log_path = Path(cfg.logger.path).expanduser()

    if not log_path.is_absolute():
        log_path = data_root() / log_path

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

    from PySide6.QtCore import QTimer, QCoreApplication
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
    from src.ui.resources import app_icon, apply_theme
    app.setWindowIcon(app_icon())
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
        
        shutdown_requested = False
        
        def handle_signal(signum, frame):
            nonlocal shutdown_requested
            if shutdown_requested:
                ctx.log.warning("APP", "Force quit (signal received multiple times)")
                import os
                os._exit(0)
            shutdown_requested = True
            ctx.log.info("APP", f"Received signal {signum}, shutting down...")
            QCoreApplication.quit()
        
        signal.signal(signal.SIGINT, handle_signal)
        signal.signal(signal.SIGTERM, handle_signal)
        
        if args.smoke_test:
            def finish_smoke_test():
                controller.shutdown()
                app.quit()

            QTimer.singleShot(1200, finish_smoke_test)
        ctx.log.info("APP", "Qt application started")
        result = app.exec()
        return ExitCode.OK if result == 0 and not callback_failed else ExitCode.FAILURE
    finally:
        controller.shutdown()
        sys.excepthook = previous_hook


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)

    if args.build:
        return build_exe()

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
