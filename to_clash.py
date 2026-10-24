#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
to_clash.py — 把 vpngate.py 已生成的 public/sub.txt (vless:// 订阅, 与 v2ray 订阅同源)
转换成 Clash (Mihomo) 格式订阅 public/clash.yaml。

由 .github/workflows/check.yml 在 `python vpngate.py` 之后调用,
产物随 public/ 一起发布到 GitHub Pages:
    https://q284378.github.io/zhuzhaiip/clash.yaml
节点与 sub.txt 完全一致, 流水线每轮自动刷新。
"""
import json
import os
import sys
from urllib.parse import urlparse, parse_qs, unquote

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
SUB_PATH = sys.argv[1] if len(sys.argv) > 1 else os.path.join(BASE_DIR, "public", "sub.txt")
OUT_PATH = sys.argv[2] if len(sys.argv) > 2 else os.path.join(BASE_DIR, "public", "clash.yaml")


def q(s):
    """JSON 字符串是合法的 YAML 双引号标量, 借用它做安全引用。"""
    return json.dumps(str(s), ensure_ascii=False)


def parse_vless(link):
    u = urlparse(link)
    if u.scheme != "vless" or not u.hostname:
        return None
    params = {k: v[0] for k, v in parse_qs(u.query).items()}
    name = unquote(u.fragment) or u.hostname
    proxy = {
        "name": name,
        "type": "vless",
        "server": u.hostname,
        "port": u.port or 443,
        "uuid": u.username or "",
        "network": params.get("type", "ws"),
        "tls": params.get("security", "") == "tls",
        "udp": True,
    }
    sni = params.get("sni") or params.get("host")
    if sni:
        proxy["servername"] = sni
    if params.get("fp"):
        proxy["client-fingerprint"] = params["fp"]
    if proxy["network"] == "ws":
        ws_opts = {}
        if params.get("path"):
            ws_opts["path"] = params["path"]
        if params.get("host"):
            ws_opts["headers"] = {"Host": params["host"]}
        if ws_opts:
            proxy["ws-opts"] = ws_opts
    return proxy


def flow_map(d):
    parts = []
    for k, v in d.items():
        if isinstance(v, dict):
            parts.append(f"{k}: {flow_map(v)}")
        elif isinstance(v, bool):
            parts.append(f"{k}: {'true' if v else 'false'}")
        elif isinstance(v, int):
            parts.append(f"{k}: {v}")
        else:
            parts.append(f"{k}: {q(v)}")
    return "{" + ", ".join(parts) + "}"


def main():
    with open(SUB_PATH, "r", encoding="utf-8") as f:
        lines = [ln.strip() for ln in f]
    header_note = ""
    links = []
    for ln in lines:
        if ln.startswith("#") and "自动更新" in ln:
            header_note = ln.lstrip("# ").strip()
        if ln.startswith("vless://"):
            links.append(ln)

    proxies, seen = [], set()
    for link in links:
        p = parse_vless(link)
        if not p:
            continue
        name = p["name"]
        if name in seen:  # 重名加序号后缀, 保证 Clash 里唯一
            i = 2
            while f"{name}-{i}" in seen:
                i += 1
            p["name"] = f"{name}-{i}"
        seen.add(p["name"])
        proxies.append(p)

    if not proxies:
        raise SystemExit("sub.txt 里没有可用的 vless:// 节点, 不生成 clash.yaml")

    names = [p["name"] for p in proxies]
    out = []
    out.append("# zhuzhaiip Clash 订阅 (Mihomo) — 节点与 v2ray 订阅 sub.txt 同源, 随流水线自动更新")
    if header_note:
        out.append(f"# {header_note}")
    out.append(f"# 节点数: {len(proxies)}")
    out.append("mixed-port: 7890")
    out.append("allow-lan: false")
    out.append("mode: rule")
    out.append("log-level: info")
    out.append("proxies:")
    for p in proxies:
        out.append(f"  - {flow_map(p)}")
    out.append("proxy-groups:")
    out.append(f"  - {{name: {q('自动选择')}, type: url-test, url: {q('http://www.gstatic.com/generate_204')}, interval: 300, tolerance: 80, proxies: [{', '.join(q(n) for n in names)}]}}")
    out.append(f"  - {{name: {q('节点选择')}, type: select, proxies: [{q('自动选择')}, {', '.join(q(n) for n in names)}, DIRECT]}}")
    out.append("rules:")
    out.append("  - MATCH,节点选择")
    text = "\n".join(out) + "\n"

    os.makedirs(os.path.dirname(OUT_PATH), exist_ok=True)
    with open(OUT_PATH, "w", encoding="utf-8") as f:
        f.write(text)
    print(f"clash.yaml 已生成: {OUT_PATH} ({len(proxies)} 个节点)")


if __name__ == "__main__":
    main()
