# -*- coding: utf-8 -*-
"""Server酱（微信推送）通道。

注册：sct.ftqq.com 免费获取 SENDKEY。API：
  POST https://sctapi.ftqq.com/{SENDKEY}.send
  字段：title（必填）、desp（正文，支持 Markdown）
"""

import requests



class ServerChanPusher:
    name = "serverchan"

    def __init__(self, *, sendkey: str | None = None):
        self.sendkey = '' if sendkey is None else sendkey

    def available(self) -> bool:
        return bool(self.sendkey)

    def send(self, title: str, content: str) -> None:
        resp = requests.post(
            f"https://sctapi.ftqq.com/{self.sendkey}.send",
            data={"title": title[:32], "desp": content},
            timeout=15,
            allow_redirects=False,
        )
        if resp.status_code != 200: raise RuntimeError('渠道 HTTP 请求失败')
        data = resp.json()
        if data.get("code") != 0:
            raise RuntimeError(f"Server酱返回错误: {data}")
