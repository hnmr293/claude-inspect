import os
import time
import subprocess
import logging

from claco.sender import Sender

from claude_inspect.script_wrapper import wrap_script_code, wrap_script_file
import claude_inspect.win as win


logger = logging.getLogger(__name__)


def _load_scripts(
    scripts: str | list[str] | None,
    replace: dict[str, str] | None = None,
) -> list[str]:
    if scripts is None:
        return []
    if isinstance(scripts, str):
        scripts = [scripts]
    result = []
    for script in scripts:
        assert os.path.exists(script), f"File not found: {script}"
        code = wrap_script_file(script)
        for k, v in (replace or {}).items():
            code = code.replace(k, v)
        result.append(code)
    return result


class ClaudeDesktopProcess:
    """Claude for Desktop の操作を行うクラス"""

    def __init__(
        self,
        exe_path: str,
        wd: str,
        inject_script: str | None = None,
    ):
        self.exe_path = exe_path
        self.wd = wd
        self.inject_script = inject_script
        self._pid = None
        self._dev_tools_pid = None
        self._keysender = Sender()
        self.MAIN_APP_TITLE = "Claude"
        self.DEVTOOLS_TITLE = "Developer Tools - https://claude.ai/"

    def _open_claude(self, timeout=3.0):
        env = os.environ.copy()
        env["CLAUDE_DEV_TOOLS"] = "detach"
        # env["CLAUDE_DEV"] = "1"

        startupinfo = subprocess.STARTUPINFO()
        # ウィンドウを最小化するフラグを設定
        startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW
        startupinfo.wShowWindow = 6  # SW_MINIMIZE

        process = subprocess.Popen(
            [
                self.exe_path,
                # f"--remote-debugging-port={self.port}",
                # f"--remote-allow-origins=http://localhost:{self.port}",
            ],
            cwd=self.wd,
            env=env,
            startupinfo=startupinfo,
        )

        if process.poll() is not None:
            raise RuntimeError("Failed to start process")

        # ウィンドウが表示されるまで待機
        t0 = time.time()
        hwnd_main = None
        hwnd_dev_tools = None
        while time.time() - t0 < timeout:
            if hwnd_main is None:
                hwnd_main = win.find_window_by_title(self.MAIN_APP_TITLE)
            if hwnd_dev_tools is None:
                hwnd_dev_tools = win.find_window_by_title(self.DEVTOOLS_TITLE)
            if hwnd_main and hwnd_dev_tools:
                break
            time.sleep(0.01)

        if hwnd_main == hwnd_dev_tools:
            # detach できてない
            logger.warning(f"Failed to detach devtools")
            win.terminate_process(process.pid)
            return None

        pid_main = None
        pid_dev_tools = None
        if hwnd_main:
            pid_main = win.get_pid_from_hwnd(hwnd_main)
        if hwnd_dev_tools:
            pid_dev_tools = win.get_pid_from_hwnd(hwnd_dev_tools)
        if not pid_main or not pid_dev_tools:
            if pid_main:
                win.terminate_process(pid_main)
            if pid_dev_tools and (pid_main is None or pid_main != pid_dev_tools):
                win.terminate_process(pid_dev_tools)
            logger.warning(f"Failed to detect main window and/or devtools window")
            return None

        # Console を表示してスクリプトを注入
        if self.inject_script:
            time.sleep(3)
            win.click_window_at_position(hwnd_dev_tools, 146, 14)  # Console タブをクリック
            h, e = self._keysender.sends(
                self.MAIN_APP_TITLE,
                [(self.inject_script, False), ("{Enter}", True)],
                window_title=self.DEVTOOLS_TITLE,
            )
            if not h:
                logger.warning(f"Failed to send keys: {e}")
            time.sleep(1)

        win.minimize_window(hwnd_main)
        win.minimize_window(hwnd_dev_tools)

        return pid_main, pid_dev_tools

    def start(self):
        if self._pid is not None or self._dev_tools_pid is not None:
            raise RuntimeError(f"Process already started: {self._pid}, {self._dev_tools_pid}")

        RETRY = 3
        result = None
        for retry in range(RETRY):
            result = self._open_claude()
            if result is not None:
                break
            logger.warning(f"{retry}/{RETRY}: failed to detect main window and/or devtools window, retrying...")
            time.sleep(0.5)
        if result is None:
            raise RuntimeError("Failed to start process")

        pid_main, pid_dev_tools = result
        logger.info(f"{pid_main=}, {pid_dev_tools=}")
        self._pid = pid_main
        self._dev_tools_pid = pid_dev_tools

    def stop(self):
        if self._pid is None:
            raise RuntimeError("Process not started")
        exitcode = win.terminate_process(self._pid)
        if self._pid != self._dev_tools_pid:
            win.terminate_process(self._dev_tools_pid)
        if exitcode is None:
            raise RuntimeError("Failed to terminate process")
        logger.info(f"{exitcode=}")
        self._pid = None
        self._dev_tools_pid = None
        return exitcode

    def __enter__(self):
        self.start()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.stop()
