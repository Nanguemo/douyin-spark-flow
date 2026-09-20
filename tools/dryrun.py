"""干跑：只扫描会话列表并匹配目标，不发送任何消息。

用于在真正发消息之前确认：登录态通过、会话列表可扫描、目标好友能被正确命中。
"""
import os
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

if os.path.exists(os.path.join(HERE, ".env")):
    from dotenv import load_dotenv

    load_dotenv(os.path.join(HERE, ".env"))

# 强制无头：干跑在后台执行，且 GitHub Actions 上跑的就是无头环境
os.environ["DEBUG"] = "false"
os.environ["CLOAKBROWSER_AUTO_UPDATE"] = "false"

from utils.config import get_config, get_userData  # noqa: E402
from utils.logger import setup_logger  # noqa: E402
from core.browser import get_browser  # noqa: E402
from core.douyin_im import DouyinIM, STATUS_READY, norm  # noqa: E402

config = get_config()
users = get_userData()
logger = setup_logger(level=config.get("logLevel", "Info"))


def main():
    u = users[0]
    # 归一化与 tasks.py 保持一致
    targets = [t for t in map(norm, u["targets"]) if t]
    print("=" * 72)
    print(f"账号: {u['username']}   目标数: {len(targets)}   fingerprint: {u['fingerprint']}")
    print("=" * 72)

    browser = get_browser(u.get("fingerprint"))
    t0 = time.time()
    try:
        context = browser.new_context()
        context.set_default_navigation_timeout(config["browserActionTimeout"])
        context.set_default_timeout(config["browserActionTimeout"])
        page = context.new_page()
        context.add_cookies(u["cookies"])

        im = DouyinIM(
            page,
            timeout=config["imScanTimeout"],
            ready_timeout=config["imReadyTimeout"],
            settle_ms=config["friendListSettleMs"],
            max_steps=config["imMaxSteps"],
        )

        res = im.wait_ready()
        print()
        print("── 门禁结果 " + "─" * 58)
        print(f"status = {res.get('status')}")
        print(f"user_id = {res.get('user_id')}   nickname = {res.get('nickname')}")
        if res.get("status") != STATUS_READY:
            print(f"[FAIL] 门禁未通过: {res}")
            return 1
        print("[OK] 登录态与会话列表均就绪")

        print()
        print("── 扫描匹配（不发送） " + "─" * 50)
        found = []
        for friend in im.iter_find_and_select(targets):
            found.append(friend)
            print(
                f"  ✅ 命中 {friend['display']!r}"
                f"  uid={friend.get('uid')} conv_id={friend.get('conv_id')}"
            )

        scan = im.last_scan or {}
        print()
        print("── 扫描统计 " + "─" * 58)
        print(f"停止原因={scan.get('stopped')}  步数={scan.get('steps')}  访问会话={scan.get('visited')}")
        print(f"命中 {len(found)}/{len(targets)}")
        missing = scan.get("missing") or []
        if missing:
            print(f"未找到({len(missing)}): {missing}")
            print(f"  备注: {scan.get('note')}")
        sel = scan.get("select_failed")
        if sel:
            print(f"找到但选中失败: {sel}")

        folds = im.fold_groups()
        if any(v for v in folds.values() if v):
            print(f"[WARN] 折叠/陌生人组有内容: {folds}")

        print()
        print(f"[OK] 干跑结束，耗时 {time.time() - t0:.1f}s（未发送任何消息）")
        return 0
    finally:
        browser.close()


if __name__ == "__main__":
    sys.exit(main())
