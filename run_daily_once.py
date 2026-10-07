"""每天最多成功运行一次续火花，并在出现异常时主动提醒。

用途：
  - 每天 0:00 定时任务调用它
  - 电脑开机时也调用它（错过补跑）
两者共用同一个「今日已完成」标记，所以不管触发几次、什么时候触发，
一天最多只发一轮，避免重复发送惊动好友或触发风控。

注意：只有**成功**（退出码 0）才写标记，失败不写，这样下次触发会重试。

★ 失败预警（2026-10-07 新增）
实测发现抖音风控的固定套路：**先让部分发送拿不到回执（"发送失败>0"），
隔天就注销登录态（Cookie 失效）**。所以这里在每次运行后检查日志，
一旦出现「发送失败>0」或「登录已失效」，就：
  1) 在桌面写一个醒目的提醒文件
  2) 弹一条 Windows 通知
让用户有时间提前导出新 Cookie，而不是等火花断了才发现。
"""
import os
import re
import subprocess
import sys
from datetime import datetime

ROOT = os.path.dirname(os.path.abspath(__file__))
LOG_DIR = os.path.join(ROOT, "logs")
STAMP = os.path.join(LOG_DIR, "last_success_date.txt")
APP_LOG = os.path.join(LOG_DIR, "app.log")
ALERT_STAMP = os.path.join(LOG_DIR, "last_cookie_alert.txt")

# 后台运行时不弹黑框
_NO_WINDOW = 0x08000000 if os.name == "nt" else 0


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


def latest_scan_result():
    """从 app.log 末尾找当天最后一条「扫描结束」，返回 (失败数, 成功数) 或 None。

    app.log 可能很大，只读最后 200KB。
    """
    if not os.path.exists(APP_LOG):
        return None
    try:
        size = os.path.getsize(APP_LOG)
        with open(APP_LOG, "rb") as f:
            f.seek(max(0, size - 200_000))
            tail = f.read().decode("utf-8", "replace")
    except Exception:
        return None

    d = today()
    fails = oks = 0
    hit = False
    for line in tail.splitlines():
        if d not in line or "扫描结束" not in line:
            continue
        m1 = re.search(r"发送成功=(\d+)", line)
        m2 = re.search(r"发送失败=(\d+)", line)
        if m1 and m2:
            oks, fails, hit = int(m1.group(1)), int(m2.group(1)), True
    return (fails, oks) if hit else None


def login_expired_today():
    """当天日志里是否出现过登录失效。"""
    if not os.path.exists(APP_LOG):
        return False
    try:
        size = os.path.getsize(APP_LOG)
        with open(APP_LOG, "rb") as f:
            f.seek(max(0, size - 200_000))
            tail = f.read().decode("utf-8", "replace")
    except Exception:
        return False
    d = today()
    return any(d in l and "登录已失效" in l for l in tail.splitlines())


def send_alert(title, body):
    """桌面提醒文件 + Windows 通知。同一天只提醒一次。"""
    if os.path.exists(ALERT_STAMP):
        try:
            if open(ALERT_STAMP, encoding="utf-8").read().strip() == today():
                log("今天已提醒过，不重复提醒")
                return
        except Exception:
            pass

    # 1) 桌面放一个醒目文件
    desktop = None
    home = os.path.expanduser("~")
    for cand in (os.path.join(home, "Desktop"),
                 os.path.join(home, "OneDrive", "Desktop"),
                 os.path.join(home, "OneDrive", "桌面"),
                 os.path.join(home, "桌面")):
        if os.path.isdir(cand):
            desktop = cand
            break
    if desktop:
        try:
            path = os.path.join(desktop, f"⚠️ 抖音火花提醒 - {title}.txt")
            with open(path, "w", encoding="utf-8") as f:
                f.write(f"{title}\n\n{body}\n\n"
                        f"（提醒时间 {datetime.now():%Y-%m-%d %H:%M}）\n"
                        f"处理办法：重新登录 douyin.com → 导出 Cookie → 发给助手更新。\n")
            log(f"已生成桌面提醒文件：{path}")
        except Exception as e:
            log(f"写桌面提醒文件失败：{e}")

    # 2) Windows 通知
    try:
        ps_script = (
            "[Windows.UI.Notifications.ToastNotificationManager, Windows.UI.Notifications,"
            " ContentType=WindowsRuntime] > $null;"
            "[Windows.Data.Xml.Dom.XmlDocument, Windows.Data.Xml.Dom.XmlDocument,"
            " ContentType=WindowsRuntime] > $null;"
            "$t=@'"
            '<toast><visual><binding template="ToastText02">'
            f'<text id="1">{title}</text><text id="2">{body}</text>'
            "</binding></visual></toast>"
            "'@;"
            "$x=New-Object Windows.Data.Xml.Dom.XmlDocument;$x.LoadXml($t);"
            "$n=New-Object Windows.UI.Notifications.ToastNotification $x;"
            "[Windows.UI.Notifications.ToastNotificationManager]::CreateToastNotifier"
            "('DouYinSparkFlow').Show($n)"
        )
        subprocess.run(["powershell", "-NoProfile", "-Command", ps_script],
                       timeout=25, creationflags=_NO_WINDOW)
        log("已发送 Windows 通知")
    except Exception as e:
        log(f"发送通知失败（不影响主流程）：{e}")

    try:
        with open(ALERT_STAMP, "w", encoding="utf-8") as f:
            f.write(today())
    except Exception:
        pass


def check_and_alert(ret):
    """运行结束后判断是否需要提醒。"""
    if login_expired_today():
        send_alert(
            "登录已失效，火花今晚可能断",
            "抖音登录态已失效，今天的火花没发出去。请尽快重新登录并导出新 Cookie。",
        )
        return

    res = latest_scan_result()
    if not res:
        return
    fails, oks = res
    if fails > 0:
        send_alert(
            f"Cookie 可能快到期了（今天 {fails} 个发送失败）",
            f"今天成功 {oks} 个、失败 {fails} 个。按以往规律，"
            f"出现发送失败后 1~2 天内登录态就会失效，建议提前导出新 Cookie。",
        )
    elif ret != 0:
        send_alert("本轮回执异常", "任务退出码非 0，但未解析到发送统计，建议查看 logs/app.log。")


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

    try:
        check_and_alert(ret)
    except Exception as e:
        log(f"预警检查出错（不影响主流程）：{e}")
    return ret


if __name__ == "__main__":
    sys.exit(main())
