"""登录态判定回归测试（scrape_ssr）。

背景
----
抖音 chat 页的 SSR 里同时存在两类身份字段：

  * `odin.user_id` —— **匿名访客 ID**。未登录时照样有值，且每次刷新都随机
    （实测三次：1993873787982888 / 1817951927286760 / 2574415927984608），
    **不能代表登录态**。
  * `user.isLogin` / `not_exist_login_cookie` / `user.statusCode` —— 权威信号。
    `statusCode: 8` 是官方 ERROR_USER_NOT_LOGIN。

旧实现把 `if out["user_id"]` 排在判定链首位，于是 odin 的匿名 ID 总能抢先命中，
导致未登录恒判 logged_in：不报「Cookie 失效」、不提前退出，一路空转到
IM_READY_TIMEOUT 超时后静默失败。

本测试锁死「明确否定信号优先」的顺序，防止后续改动再把它退回去。
"""

import os
import sys

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from core.douyin_im import scrape_ssr  # noqa: E402


# 未登录页面的真实片段（取自 https://www.douyin.com/chat 的 SSR 快照）
# 注意 odin 里带着 not_exist_login_cookie:true，同时有随机 visitor id
LOGGED_OUT_HTML = r"""
<script nonce="">
if ("visible" === document.visibilityState) {
  setPageViewLog({"odin":"{\"user_id\":\"2574415927984608\",\"user_type\":12,\"user_is_auth\":0,\"user_unique_id\":\"7687273427807700514\",\"not_exist_login_cookie\":true}"});
  document.removeEventListener("visibilitychange", e);
};
</script>
<script nonce="">
window._SSR_DATA = "%22user%22%3A%7B%22isLogin%22%3Afalse%2C%22statusCode%22%3A8%2C%22isSpider%22%3Afalse%7D%2C%22innerLink%22";
</script>
"""

# 已登录：isLogin=true，user.info 给出真实 uid / secUid，odin 不带否定标记
LOGGED_IN_HTML = r"""
<script nonce="">
window._ROUTER_DATA = {"loaderData":{"chat-page":{"user":{"isLogin":true,
"info":{"uid":"7123456789012345671","secUid":"MS4wLjABAAAAaaaabbbbccccdddd",
"nickname":"测试用户"}},
"odin":"{\"user_id\":\"7123456789012345671\",\"user_type\":1,\"user_is_auth\":1,\"user_unique_id\":\"8888888888888888888\"}"}}};
</script>
"""

# Cookie 失效：有 sessionid 但服务端不认（statusCode 8），odin 标记无登录 cookie
EXPIRED_HTML = r"""
<script nonce="">
window._ROUTER_DATA = {"loaderData":{"chat-page":{"user":{"isLogin":false,"statusCode":8,"isSpider":false},
"odin":"{\"user_id\":\"9999888877776666555\",\"user_type\":12,\"user_is_auth\":0,\"not_exist_login_cookie\":true}"}}};
</script>
"""


@pytest.mark.parametrize(
    "label,html,expect",
    [
        ("未登录", LOGGED_OUT_HTML, "logged_out"),
        ("已登录", LOGGED_IN_HTML, "logged_in"),
        ("Cookie 失效", EXPIRED_HTML, "logged_out"),
    ],
)
def test_verdict(label, html, expect):
    got = scrape_ssr(html)["verdict"]
    assert got == expect, f"{label}: verdict={got}, 期望 {expect}"


def test_logged_out_is_not_mistaken_for_login():
    """核心回归：odin 匿名 ID 存在时，不能判成已登录。"""
    r = scrape_ssr(LOGGED_OUT_HTML)
    assert r["verdict"] == "logged_out"
    # 匿名访客 ID 应被单独暴露，便于日志区分
    assert r["visitor_id"] == "2574415927984608"
    assert r["sec_uid"] is None
    assert r["raw"]["login_status_code"] == "8"


def test_logged_in_keeps_real_uid():
    """防修过头：真正的登录必须仍然判 logged_in，且 uid 取真值。"""
    r = scrape_ssr(LOGGED_IN_HTML)
    assert r["verdict"] == "logged_in"
    assert r["user_id"] == "7123456789012345671"
    assert r["sec_uid"] == "MS4wLjABAAAAaaaabbbbccccdddd"


def test_uid_prefers_real_uid_over_visitor_id():
    """真 uid 优先于 odin 匿名 ID，避免会话里解析错对方 uid。"""
    r = scrape_ssr(LOGGED_IN_HTML)
    assert r["user_id"] == r["raw"]["uid"]
