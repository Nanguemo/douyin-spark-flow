"""每天最多成功运行一次续火花。

用途：
  - 9:00 定时任务调用它
  - 电脑开机时（配合智能插座远程开机）也调用它
两者共用同一个「今日已完成」标记，所以不管触发几次、什么时候触发，
一天最多只发一轮，避免重复发送惊动好友或触发风控。

注意：只有**成功**（退出码 0）才写标记，失败不写，
这样下一次触发会重试。
"""
import os
import subprocess
import sys
from datetime import datetime

ROOT = os.path.dirname(os.path.abspath(__file__))
LOG_DIR = os.path.join(ROOT, "logs")
STAMP = os.path.join(LOG_DIR, "last_success_date.txt")


def log(msg):
    print(f"[{datetime.now():%Y-%m-%d %H:%M:%S}] {msg}", flush=True)


def today():
    return datetime.now().strftime("%Y-%m-%d")


def already_done():
    try:
        with open(STAMP, encoding="utf-8") as f:
            return f.read().strip() == today()
    except FileNotFoundError:
        return False


def mark_done():
    os.makedirs(LOG_DIR, exist_ok=True)
    with open(STAMP, "w", encoding="utf-8") as f:
        f.write(today())


def main():
    os.makedirs(LOG_DIR, exist_ok=True)
    if already_done():
        log(f"今天（{today()}）已经成功续过火花，跳过本次触发")
        return 0

    log(f"今天（{today()}）尚未续火花，开始执行")
    ret = subprocess.call(
        [sys.executable, os.path.join(ROOT, "main.py"), "task"], cwd=ROOT)
    if ret == 0:
        mark_done()
        log("续火花成功，已标记今日完成")
    else:
        log(f"续火花失败（退出码 {ret}），不写标记，下次触发会重试")
    return ret


if __name__ == "__main__":
    sys.exit(main())
