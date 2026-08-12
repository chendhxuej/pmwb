"""诊断：捕获需求页实际发出的网络请求及状态码。"""
import base64
import json
import subprocess
import sys
import time

import websocket
import urllib.request

CHROME = r"C:\Program Files\Google\Chrome\Application\chrome.exe"
PORT = 9225
URL = "http://localhost:5173/requirement"

_counter = {"id": 0}


def _next_id():
    _counter["id"] += 1
    return _counter["id"]


def rpc(ws, method, params=None, expect=True):
    mid = _next_id()
    ws.send(json.dumps({"id": mid, "method": method, "params": params or {}}))
    if not expect:
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
    for p in pages:
        if p["type"] == "page":
            return p["webSocketDebuggerUrl"]
    raise RuntimeError("no page")


def main():
    proc = subprocess.Popen(
        [CHROME, f"--remote-debugging-port={PORT}", "--remote-allow-origins=*",
         "--headless", "--disable-gpu", "--no-first-run", "--no-default-browser-check",
         "--disable-dev-shm-usage", "--no-sandbox", "about:blank"],
        stdout=subprocess.PIPE, stderr=subprocess.PIPE,
    )
    try:
        time.sleep(2)
        ws = websocket.create_connection(get_ws_url(), timeout=20)
        ws.settimeout(2)
        for dom in ("Page", "DOM", "Network", "Runtime"):
            rpc(ws, f"{dom}.enable")
        try:
            while True:
                ws.recv()
        except websocket.WebSocketTimeoutException:
            pass

        rpc(ws, "Page.navigate", {"url": URL})
        # wait load
        deadline = time.time() + 15
        while time.time() < deadline:
            try:
                msg = json.loads(ws.recv())
            except websocket.WebSocketTimeoutException:
                continue
            if msg.get("method") == "Page.loadEventFired":
                break
        time.sleep(3)

        # drain network responses
        print("=== Network responses ===")
        deadline = time.time() + 8
        while time.time() < deadline:
            try:
                msg = json.loads(ws.recv())
            except websocket.WebSocketTimeoutException:
                continue
            m = msg.get("method")
            if m == "Network.responseReceived":
                resp = msg["params"]["response"]
                print(f"  {resp['status']} {resp.get('url')}")
            elif m == "Network.requestFailed":
                req = msg["params"].get("requestId", "")
                print(f"  FAILED reqId={req}")
    finally:
        proc.terminate()
        try:
            proc.wait(timeout=5)
        except subprocess.TimeoutExpired:
            proc.kill()


if __name__ == "__main__":
    main()
