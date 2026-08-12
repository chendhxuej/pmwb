"""产品圣经 docx 页面浏览器冒烟测试。"""
import base64
import json
import os
import subprocess
import sys
import time

import websocket
import urllib.request

CHROME = r"C:\Program Files\Google\Chrome\Application\chrome.exe"
PORT = 9225
BASE = "http://localhost:5173"
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


def eval_expr(ws, expr):
    res = rpc(ws, "Runtime.evaluate", {"expression": expr, "returnByValue": True, "awaitPromise": True})
    return res.get("result", {}).get("result", {}).get("value")


def wait_for(ws, expr, timeout=15):
    deadline = time.time() + timeout
    while time.time() < deadline:
        val = eval_expr(ws, f"(function(){{ try {{ return !!({expr}); }} catch {{ return false; }} }})()")
        if val:
            return True
        time.sleep(0.3)
    return False


def main():
    os.makedirs(OUTDIR, exist_ok=True)
    proc = subprocess.Popen(
        [CHROME, f"--remote-debugging-port={PORT}", "--remote-allow-origins=*",
         "--headless", "--disable-gpu", "--no-first-run", "--no-default-browser-check",
         "--disable-dev-shm-usage", "--no-sandbox", "--disable-software-rasterizer",
         "about:blank"],
        stdout=subprocess.PIPE, stderr=subprocess.PIPE,
    )
    errors = []
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

        print("===== /product-bible (e-contract docx) =====")
        rpc(ws, "Page.navigate", {"url": BASE + "/product-bible"})
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

        # 切换到电子协议
        if not wait_for(ws, "document.querySelector('.el-radio-button__inner')"):
            errors.append("目录按钮未渲染")
        else:
            eval_expr(ws, """
                (function(){
                    var el = Array.from(document.querySelectorAll('.el-radio-button__inner'))
                        .find(function(x){ return x.textContent.includes('电子协议'); });
                    if (el) el.click();
                    return !!el;
                })()
            """)
        time.sleep(2)

        # 等待内容渲染
        wait_for(ws, "document.querySelectorAll('.markdown-body table').length >= 20", timeout=15)

        # 收集 console 错误、异常、网络失败
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
            elif m == "Network.loadingFailed":
                errors.append("NETWORK: " + msg["params"].get("errorText", ""))

        # 检查指标
        metrics = {
            "toc_items": eval_expr(ws, "document.querySelectorAll('.toc-item').length") or 0,
            "tables": eval_expr(ws, "document.querySelectorAll('.markdown-body table').length") or 0,
            "images": eval_expr(ws, "document.querySelectorAll('.markdown-body img').length") or 0,
            "edit_button_exists": eval_expr(ws, "!!Array.from(document.querySelectorAll('.pb-actions button')).find(function(b){ return b.textContent.includes('编辑内容'); })") or False,
            "title": eval_expr(ws, "document.querySelector('.meta-value') && document.querySelector('.meta-value').textContent") or "",
        }

        # 搜索测试
        eval_expr(ws, """
            (function(){
                var input = document.querySelector('.toc-search-input');
                if (!input) return false;
                input.value = '协议';
                input.dispatchEvent(new Event('input'));
                return true;
            })()
        """)
        time.sleep(0.8)
        search_count = eval_expr(ws, "document.querySelectorAll('mark.bible-hl').length") or 0

        print(f"  metrics: {metrics}")
        print(f"  search hits: {search_count}")
        if errors:
            for e in errors:
                print("  " + e)
            print("  [FAIL] errors detected")
        else:
            checks = []
            if metrics["toc_items"] < 10:
                checks.append(f"TOC 项不足 ({metrics['toc_items']})")
            if metrics["tables"] < 20:
                checks.append(f"表格数不足 ({metrics['tables']})")
            if metrics["images"] < 5:
                checks.append(f"图片数不足 ({metrics['images']})")
            if metrics["edit_button_exists"]:
                checks.append("docx 页面不应出现编辑按钮")
            if search_count == 0:
                checks.append("搜索未命中")
            if checks:
                for c in checks:
                    print("  [CHECK FAIL] " + c)
            else:
                print("  [OK] docx 页面渲染通过")

        shot = rpc(ws, "Page.captureScreenshot", {"format": "png"})
        out = os.path.join(OUTDIR, "pb_e_contract.png")
        with open(out, "wb") as f:
            f.write(base64.b64decode(shot["result"]["data"]))
        print(f"  screenshot -> {out}")
        return 1 if errors or checks else 0
    finally:
        proc.terminate()
        try:
            proc.wait(timeout=5)
        except subprocess.TimeoutExpired:
            proc.kill()


if __name__ == "__main__":
    sys.exit(main())
