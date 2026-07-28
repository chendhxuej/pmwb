# -*- coding: utf-8 -*-
"""
PMWB 看门狗 / 保活脚本
- 每隔固定间隔检查所有服务端口，挂了就用已验证的控制台命令自动拉起。
- 依赖顺序：后端(8000)、Master(8001) 依赖 MySQL(3306)，MySQL 未就绪时不启动后端/Master（下一轮再起）。
- 用法：
    python pmwb-keeper.py          # 常驻保活（默认，Ctrl+C 或关窗口停止）
    python pmwb-keeper.py --once   # 单轮拉起并等待就绪后退出（用于验证/一次性启动）
"""
import subprocess, socket, time, os, sys, datetime

DETACH = getattr(subprocess, "DETACHED_PROCESS", 0) | getattr(subprocess, "CREATE_NEW_PROCESS_GROUP", 0)

LOG_DIR = r"C:\pmwb-logs"
LOG = os.path.join(LOG_DIR, "keeper.log")
try:
    os.makedirs(LOG_DIR, exist_ok=True)
except Exception:
    pass

# ---- 各服务的启动参数（均为此前多次验证可用的控制台命令）----
MYSQLD   = r"C:\mysql\mysql-8.0.46-winx64\bin\mysqld.exe"
MYINI    = r"C:\mysql\mysql-8.0.46-winx64\my.ini"
BE_PY    = r"D:\项目\个人工作台系统\backend\venv\Scripts\python.exe"
BE_CWD   = r"D:\项目\个人工作台系统\backend"
NODE     = r"C:\Users\chend\.workbuddy\binaries\node\versions\22.22.2\node.exe"
FE_CWD   = r"D:\项目\个人工作台系统\frontend"
MAIL_CWD = r"D:\项目\统一邮件中心\server"
MASTER_CWD = r"D:\项目\个人工作台系统\services\master\app"

SERVICES = [3306, 8000, 5173, 3210, 8001]
NAMES = {3306: "MySQL", 8000: "Backend", 5173: "Frontend", 3210: "Mail", 8001: "Master"}


def log(msg):
    line = "[%s] %s" % (datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S"), msg)
    try:
        sys.stdout.write(line + "\n")
        sys.stdout.flush()
    except Exception:
        pass
    try:
        with open(LOG, "a", encoding="utf-8") as f:
            f.write(line + "\n")
    except Exception:
        pass


def port_up(port):
    try:
        with socket.create_connection(("127.0.0.1", port), timeout=1):
            return True
    except OSError:
        return False


def spawn(cmd, cwd=None):
    si = subprocess.STARTUPINFO()
    si.dwFlags |= subprocess.STARTF_USESHOWWINDOW
    si.wShowWindow = 0  # SW_HIDE，后台隐藏运行
    return subprocess.Popen(
        cmd, cwd=cwd, startupinfo=si, creationflags=DETACH,
        stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, close_fds=True,
    )


def _mysql_process_running():
    # 避免重复拉起多个 mysqld 争抢数据目录锁（崩溃恢复时会陷入死循环）
    try:
        out = subprocess.run(
            [r"C:\Windows\System32\tasklist.exe", "/FI", "IMAGENAME eq mysqld.exe"],
            capture_output=True, text=True, timeout=5,
        ).stdout
        return "mysqld.exe" in out
    except Exception:
        return False


def ensure_mysql():
    if port_up(3306):
        return
    if _mysql_process_running():
        # mysqld 已在运行但端口尚未就绪（可能在做 InnoDB 崩溃恢复），耐心等待，不要重复拉起
        return
    log("MySQL(3306) down -> starting mysqld")
    # mysqld 是控制台子系统程序，必须由带控制台的父进程(python.exe)拉起；
    # 若用 pythonw(无控制台)启动看门狗，--console 会因缺少控制台而静默失败。
    # 因此开机/手动启动看门狗都必须用 python.exe（桌面 .bat 与开机 vbs 均已用 python.exe）。
    mlog_path = os.path.join(LOG_DIR, "mysqld.log")
    try:
        mlog = open(mlog_path, "ab")
    except Exception:
        mlog = subprocess.DEVNULL
    subprocess.Popen(
        [MYSQLD, "--defaults-file=%s" % MYINI, "--console"],
        creationflags=DETACH,
        stdout=mlog, stderr=subprocess.STDOUT, close_fds=True,
    )


def ensure_mail():
    if port_up(3210):
        return
    log("Mail(3210) down -> starting tsx.cmd")
    spawn(["cmd", "/c", r"node_modules\.bin\tsx.cmd", "src/index.ts"], cwd=MAIL_CWD)


def ensure_frontend():
    if port_up(5173):
        return
    log("Frontend(5173) down -> starting vite.js")
    spawn([NODE, "node_modules/vite/bin/vite.js", "--host", "127.0.0.1", "--port", "5173"], cwd=FE_CWD)


def ensure_backend():
    if port_up(8000):
        return
    if not port_up(3306):
        log("Backend(8000) waits for MySQL(3306) ready ...")
        return
    log("Backend(8000) down -> starting uvicorn")
    spawn([BE_PY, "-m", "uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"], cwd=BE_CWD)


def ensure_master():
    if port_up(8001):
        return
    if not port_up(3306):
        log("Master(8001) waits for MySQL(3306) ready ...")
        return
    log("Master(8001) down -> starting uvicorn")
    spawn([BE_PY, "-m", "uvicorn", "main:app", "--host", "127.0.0.1", "--port", "8001"], cwd=MASTER_CWD)


def cycle():
    ensure_mysql()
    ensure_mail()
    ensure_frontend()
    ensure_backend()
    ensure_master()


def status_str():
    return "  ".join("%s(%d)=%s" % (NAMES[p], p, "UP" if port_up(p) else "DOWN") for p in SERVICES)


def run_once(wait_seconds=90):
    log("===== PMWB keeper single-pass start =====")
    t0 = time.time()
    while time.time() - t0 < wait_seconds:
        cycle()
        if all(port_up(p) for p in SERVICES):
            log("ALL UP: " + status_str())
            log("===== single-pass done =====")
            return 0
        time.sleep(3)
    log("TIMEOUT after %ss: %s" % (wait_seconds, status_str()))
    return 1


def run_forever(interval=15):
    log("===== PMWB keeper daemon start (interval=%ss) =====" % interval)
    log("close this window to stop keep-alive.")
    last_status = None
    while True:
        try:
            cycle()
            st = status_str()
            if st != last_status:
                log("STATUS: " + st)
                last_status = st
            time.sleep(interval)
        except KeyboardInterrupt:
            log("stopped by user.")
            return 0
        except Exception as e:
            log("cycle error: %s: %s" % (type(e).__name__, str(e)[:120]))
            time.sleep(interval)


if __name__ == "__main__":
    if "--once" in sys.argv:
        sys.exit(run_once())
    else:
        sys.exit(run_forever())
