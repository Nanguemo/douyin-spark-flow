"""检查 GitHub 上的「手机一键续火花」信号，有新信号就跑一次任务。

流程：
  手机在 GitHub 上手动触发 workflow → 仓库 signal/trigger.txt 被写入新的 UTC 时间戳
  本机每隔几分钟读一次该文件 → 与本地记录的旧值不同 → 执行 main.py task

刻意不使用代理：本机直连 raw.githubusercontent.com 可用（走代理反而超时），
所以先把 *_PROXY 环境变量清掉，避免 urllib 误走代理。
"""
import os
import subprocess
import sys
import urllib.request
from datetime import datetime

REPO_RAW = ("https://raw.githubusercontent.com/"
            "Nanguemo/douyin-spark-flow/main/signal/trigger.txt")

ROOT = os.path.dirname(os.path.abspath(__file__))
LOG_DIR = os.path.join(ROOT, "logs")
STATE = os.path.join(LOG_DIR, "last_signal.txt")

# 清掉代理环境变量，强制直连
for _k in ("http_proxy", "https_proxy", "HTTP_PROXY", "HTTPS_PROXY",
           "all_proxy", "ALL_PROXY"):
    os.environ.pop(_k, None)


def log(msg):
    print(f"[{datetime.now():%Y-%m-%d %H:%M:%S}] {msg}", flush=True)


def read_remote():
    req = urllib.request.Request(
        REPO_RAW, headers={"User-Agent": "curl/8.0", "Cache-Control": "no-cache"})
    with urllib.request.urlopen(req, timeout=25) as r:
        return r.read().decode("utf-8", "replace").strip()


def read_local():
    try:
        with open(STATE, encoding="utf-8") as f:
            return f.read().strip()
    except FileNotFoundError:
        return ""


def main():
    os.makedirs(LOG_DIR, exist_ok=True)

    try:
        remote = read_remote()
    except Exception as e:
        log(f"读取信号失败（跳过本次）：{type(e).__name__}: {e}")
        return 0

    local = read_local()
    if not remote:
        log("远端无信号，跳过")
        return 0
    if remote == local:
        log(f"无新信号（最近一次已处理：{local}）")
        return 0

    log(f"发现新信号 {remote}，开始执行续火花")
    # 先落盘再执行，避免执行期间重复触发
    with open(STATE, "w", encoding="utf-8") as f:
        f.write(remote)

    ret = subprocess.call(
        [sys.executable, os.path.join(ROOT, "main.py"), "task"], cwd=ROOT)
    log(f"续火花执行完毕，退出码={ret}")
    return ret


if __name__ == "__main__":
    sys.exit(main())
