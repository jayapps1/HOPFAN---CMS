"""Observe actual desktop startup and close only the process launched here."""
import ctypes
from ctypes import wintypes
import json
from pathlib import Path
import subprocess
import sys
import time

ROOT=Path(__file__).resolve().parents[1]
def main():
    if sys.platform!='win32':raise SystemExit('Run this desktop check on Windows.')
    process=subprocess.Popen([str(ROOT/'.venv/Scripts/python.exe'),str(ROOT/'hopfan.py')],cwd=ROOT,
        stdout=subprocess.PIPE,stderr=subprocess.PIPE,text=True,creationflags=subprocess.CREATE_NO_WINDOW)
    user32=ctypes.windll.user32
    user32.GetWindowThreadProcessId.argtypes=[wintypes.HWND,ctypes.POINTER(wintypes.DWORD)]
    user32.GetWindowTextW.argtypes=[wintypes.HWND,wintypes.LPWSTR,ctypes.c_int]
    user32.PostMessageW.argtypes=[wintypes.HWND,wintypes.UINT,wintypes.WPARAM,wintypes.LPARAM]
    user32.ShowWindow.argtypes=[wintypes.HWND,ctypes.c_int]
    callback_type=ctypes.WINFUNCTYPE(wintypes.BOOL,wintypes.HWND,wintypes.LPARAM)
    user32.EnumWindows.argtypes=[callback_type,wintypes.LPARAM]
    window=None; deadline=time.monotonic()+20
    try:
        while time.monotonic()<deadline and window is None:
            if process.poll() is not None:raise RuntimeError('Desktop exited during startup.')
            command=f"Get-CimInstance Win32_Process -Filter 'ParentProcessId = {process.pid}' | Select-Object -ExpandProperty ProcessId | ConvertTo-Json -Compress"
            children=subprocess.run(['powershell','-NoProfile','-Command',command],capture_output=True,text=True,creationflags=subprocess.CREATE_NO_WINDOW)
            parsed=json.loads(children.stdout) if children.stdout.strip() else []
            owned={process.pid,*([parsed] if isinstance(parsed,int) else parsed)}
            def find(hwnd,_):
                pid=wintypes.DWORD();user32.GetWindowThreadProcessId(hwnd,ctypes.byref(pid))
                title=ctypes.create_unicode_buffer(256);user32.GetWindowTextW(hwnd,title,256)
                if pid.value in owned and 'HOPFAN' in title.value:
                    nonlocal window
                    window=hwnd
                return True
            user32.EnumWindows(callback_type(find),0)
            time.sleep(.5)
        if window is None:raise RuntimeError('Desktop window was not found.')
        time.sleep(3)
        user32.ShowWindow(window,0)  # Keep the observation in the background.
        until=time.monotonic()+31
        while time.monotonic()<until:
            if process.poll() is not None:raise RuntimeError('Desktop exited during observation.')
            time.sleep(.5)
        user32.PostMessageW(window,0x0010,0,0)
        stdout,stderr=process.communicate(timeout=15)
        if process.returncode!=0 or 'Traceback' in stdout+stderr:raise RuntimeError('Desktop startup/close check failed.')
        print('Actual HOPFAN desktop opened, stayed running for 31 seconds, and closed cleanly.')
    finally:
        if process.poll() is None:
            if window is not None:user32.PostMessageW(window,0x0010,0,0)
            try:process.communicate(timeout=10)
            except subprocess.TimeoutExpired:
                # Narrowly terminate only this owned process tree.
                subprocess.run(['taskkill','/PID',str(process.pid),'/T'],capture_output=True,creationflags=subprocess.CREATE_NO_WINDOW)
if __name__=='__main__':main()
