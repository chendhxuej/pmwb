"""浏览器实测：遍历各模块页面，捕获 console 错误并截图。

用法: python scripts/verify_pages.py
依赖: pip install websocket-client
"""
import base64
import json
import subprocess
import sys
import time

import websocket
import urllib.request

CHROME = r"C:\Program Files\Google\Chrome\Application\chrome.exe"
PORT = 9224
BASE = "http://localhost:5173"
ROUTES = [
    ("/", "home"),
    ("/requirement", "requirements"),
    ("/ticket", "tickets"),
    ("/meeting", "meetings"),
    ("/operation", "operation"),
    ("/knowledge", "knowledge"),
    ("/todo", "todo"),
]
OUTDIR = r"D:\项目\个人工作台系统\verify_shots"

_counter = {"id": 0}


def _next_id():
    _counter["id"] += 1
    return _counter["id"]


def rpc(ws, method, params=None, expect_response=True):
    mid = _next_id()
    ws.send(json.dumps({"id": mid, "method": method, "params": params or {}}))
    if not expect_response:
        return None
    deadline = time.time() + 15
    while time.time() < deadline:
        try:
            msg = json.loads(ws.recv())
        except websocket.WebSocketTimeoutException:
            continue
        if msg.get("id") == mid:
            return msg
    raise RuntimeError(f"no response for {method}")


def get_ws_url():
    with urllib.request.urlopen(f"http://127.0.0.1:{PORT}/json/list") as resp:
        pages = json.loads(resp.read())
    for page in pages:
        if page["type"] == "page":
            return page["webSocketDebuggerUrl"]
    raise RuntimeError("no page target found")


def wait_element(ws, selector, timeout=12):
    deadline = time.time() + timeout
    while time.time() < deadline:
        res = rpc(ws, "Runtime.evaluate",
                  {"expression": f"(function(){{return document.querySelector({json.dumps(selector)}) !== null;}})()",
                   "returnByValue": True})
        if res.get("result", {}).get("result", {}).get("value"):
            return True
        time.sleep(0.4)
    return False


def main():
    import os
    os.makedirs(OUTDIR, exist_ok=True)
    proc = subprocess.Popen(
        [CHROME, f"--remote-debugging-port={PORT}", "--remote-allow-origins=*",
         "--headless", "--disable-gpu", "--no-first-run", "--no-default-browser-check",
         "--disable-dev-shm-usage", "--no-sandbox", "--disable-software-rasterizer",
         "about:blank"],
        stdout=subprocess.PIPE, stderr=subprocess.PIPE,
    )
    try:
        time.sleep(2)
        ws = websocket.create_connection(get_ws_url(), timeout=20)
        ws.settimeout(2)
        for dom in ("Page", "DOM", "Network", "Runtime"):
            rpc(ws, f"{dom}.enable")
        # clear any pending messages
        try:
            while True:
                ws.recv()
        except websocket.WebSocketTimeoutException:
            pass

        for route, name in ROUTES:
            try:
                url = BASE + route
                print(f"\n===== {route} ({name}) =====")
                rpc(ws, "Page.navigate", {"url": url})
                # wait for load event
                loaded = False
                deadline = time.time() + 15
                while time.time() < deadline:
                    try:
                        msg = json.loads(ws.recv())
                    except websocket.WebSocketTimeoutException:
                        continue
                    if msg.get("method") == "Page.loadEventFired":
                        loaded = True
                        break
                if not loaded:
                    print("  [WARN] load event not fired")
                time.sleep(1.5)

                # collect console errors + failed network for a window
                errors = []
                deadline = time.time() + 6
                while time.time() < deadline:
                    try:
                        msg = json.loads(ws.recv())
                    except websocket.WebSocketTimeoutException:
                        continue
                    m = msg.get("method")
                    if m == "Runtime.consoleAPICalled" and msg["params"].get("type") == "error":
                        texts = [a.get("value", "") or a.get("description", "") for a in msg["params"].get("args", [])]
                        errors.append("CONSOLE: " + " ".join(filter(None, texts)))
                    elif m == "Runtime.exceptionThrown":
                        desc = msg["params"].get("exceptionDetails", {}).get("exception", {}).get("description", "")
                        errors.append("EXCEPTION: " + desc)
                for e in errors:
                    print("  " + e)

                # wait for content to render
                has_table = wait_element(ws, ".el-table__body-wrapper .el-table__row", timeout=10)
                has_app = wait_element(ws, "#app", timeout=5)
                # detect error page text
                res = rpc(ws, "Runtime.evaluate",
                          {"expression": "document.body.innerText.slice(0,200)", "returnByValue": True})
                body_text = res.get("result", {}).get("result", {}).get("value", "") or ""
                if errors:
                    print(f"  [FAIL] console errors detected")
                elif not has_app:
                    print(f"  [FAIL] #app not mounted; body={body_text!r}")
                else:
                    print(f"  [OK] mounted; table_rows={has_table}; body_preview={body_text[:60]!r}")

                # screenshot
                shot = rpc(ws, "Page.captureScreenshot", {"format": "png"})
                data = shot["result"]["data"]
                out = os.path.join(OUTDIR, f"{name}.png")
                with open(out, "wb") as f:
                    f.write(base64.b64decode(data))
                print(f"  screenshot -> {out}")
            except Exception as exc:
                print(f"  [ERROR] route {route} failed: {exc!r}")
                continue
    finally:
        proc.terminate()
        try:
            proc.wait(timeout=5)
        except subprocess.TimeoutExpired:
            proc.kill()


if __name__ == "__main__":
    main()
