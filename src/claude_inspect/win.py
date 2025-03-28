import time
import ctypes
from ctypes import wintypes

# 定数
SW_MINIMIZE = 6
PROCESS_TERMINATE = 0x0001
PROCESS_QUERY_INFORMATION = 0x0400
STILL_ACTIVE = 259

# 必要なWindows API関数を定義
user32 = ctypes.WinDLL("user32", use_last_error=True)
kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)

# 関数のプロトタイプを設定
user32.FindWindowW.restype = wintypes.HWND
user32.FindWindowW.argtypes = [wintypes.LPCWSTR, wintypes.LPCWSTR]

user32.GetWindowThreadProcessId.restype = wintypes.DWORD
user32.GetWindowThreadProcessId.argtypes = [wintypes.HWND, ctypes.POINTER(wintypes.DWORD)]

user32.ShowWindow.restype = wintypes.BOOL
user32.ShowWindow.argtypes = [wintypes.HWND, ctypes.c_int]

kernel32.OpenProcess.restype = wintypes.HANDLE
kernel32.OpenProcess.argtypes = [wintypes.DWORD, wintypes.BOOL, wintypes.DWORD]

kernel32.TerminateProcess.restype = wintypes.BOOL
kernel32.TerminateProcess.argtypes = [wintypes.HANDLE, wintypes.UINT]

kernel32.CloseHandle.restype = wintypes.BOOL
kernel32.CloseHandle.argtypes = [wintypes.HANDLE]

kernel32.GetExitCodeProcess.restype = wintypes.BOOL
kernel32.GetExitCodeProcess.argtypes = [wintypes.HANDLE, ctypes.POINTER(wintypes.DWORD)]

user32.SendMessageW.restype = ctypes.c_void_p
user32.SendMessageW.argtypes = [wintypes.HWND, wintypes.UINT, wintypes.WPARAM, wintypes.LPARAM]


def find_window_by_title(title):
    """ウィンドウタイトルからウィンドウハンドルを取得"""
    hwnd = user32.FindWindowW(None, title)
    if not hwnd:
        return None
    return hwnd


def get_pid_from_hwnd(hwnd):
    """ウィンドウハンドルからプロセスIDを取得"""
    pid = wintypes.DWORD()
    user32.GetWindowThreadProcessId(hwnd, ctypes.byref(pid))
    return pid.value


def minimize_window(hwnd):
    """ウィンドウを最小化"""
    return user32.ShowWindow(hwnd, SW_MINIMIZE)


def terminate_process(pid):
    # プロセスを開く
    h_process = kernel32.OpenProcess(PROCESS_TERMINATE | PROCESS_QUERY_INFORMATION, False, pid)
    if not h_process:
        return None

    # プロセスを終了
    exit_code_to_set = 0
    result = kernel32.TerminateProcess(h_process, exit_code_to_set)

    # 終了コードを取得
    exit_code = None
    actual_exit_code = wintypes.DWORD()
    if result:
        # プロセスが完全に終了するまで少し待機
        time.sleep(0.1)

        if kernel32.GetExitCodeProcess(h_process, ctypes.byref(actual_exit_code)):
            exit_code = actual_exit_code.value
            if exit_code == STILL_ACTIVE:
                # まだ終了していない
                exit_code = None
        else:
            # 終了コードの取得に失敗
            pass
    else:
        # 終了に失敗
        pass

    # ハンドルを閉じる
    kernel32.CloseHandle(h_process)

    return exit_code


def click_window_at_position(hwnd, x, y):
    """ウィンドウの特定位置をクリック（メッセージ送信方式）"""
    # 必要な定数
    WM_LBUTTONDOWN = 0x0201
    WM_LBUTTONUP = 0x0202
    MK_LBUTTON = 0x0001

    # 位置情報をLPARAMにパック
    lParam = (y << 16) | x

    # user32.dllをロード
    user32 = ctypes.WinDLL("user32", use_last_error=True)

    # メッセージを送信
    user32.SendMessageW(hwnd, WM_LBUTTONDOWN, MK_LBUTTON, lParam)
    user32.SendMessageW(hwnd, WM_LBUTTONUP, 0, lParam)

    return True
