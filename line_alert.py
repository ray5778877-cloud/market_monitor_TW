#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
line_alert.py — 把 backtest_2 持倉快照推播到 LINE
================================================
不再重抓 Yahoo。流程：

  1) python backtest_2.py          → 寫入 data/latest_portfolio.json
  2) python line_alert.py          → 讀 JSON，推播持倉摘要

send_mode（data/line_config.json）：
  push       只寄給 user_id
  multicast  寄給 user_id + user_ids 列表
  broadcast  寄給「所有已加 Bot 好友」的人（推薦給多人收訊）

注意：broadcast 只會寄給「當下已是好友」的人。
新朋友加完後若要收到「今天已測好的結果」，再執行一次：
  python line_alert.py
"""

from __future__ import annotations

import argparse
import datetime as dt
import json
import os
import subprocess
import sys
from pathlib import Path
from typing import Any

import requests

ROOT = Path(__file__).resolve().parent
os.chdir(ROOT)

CONFIG_PATH = ROOT / "data" / "line_config.json"
PORTFOLIO_JSON = ROOT / "data" / "latest_portfolio.json"
LOG_PATH = ROOT / "data" / "line_alert.log"
LINE_PUSH_URL = "https://api.line.me/v2/bot/message/push"
LINE_MULTICAST_URL = "https://api.line.me/v2/bot/message/multicast"
LINE_BROADCAST_URL = "https://api.line.me/v2/bot/message/broadcast"
MAX_LINE_CHARS = 4900


def _log(msg: str) -> None:
    ts = dt.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    line = f"[{ts}] {msg}"
    print(line)
    try:
        LOG_PATH.parent.mkdir(parents=True, exist_ok=True)
        with open(LOG_PATH, "a", encoding="utf-8") as f:
            f.write(line + "\n")
    except Exception:
        pass


def load_config() -> dict[str, Any]:
    if not CONFIG_PATH.exists():
        raise FileNotFoundError(
            f"找不到 {CONFIG_PATH}，請先設定 LINE token / user_id"
        )
    with open(CONFIG_PATH, "r", encoding="utf-8") as f:
        cfg = json.load(f)

    token = str(cfg.get("channel_access_token", "")).strip()
    if not token or token.startswith("請"):
        raise ValueError("line_config.json 尚未填入有效 channel_access_token")

    mode = str(cfg.get("send_mode", "push")).strip().lower()
    if mode not in ("push", "multicast", "broadcast"):
        raise ValueError("send_mode 必須是 push / multicast / broadcast")

    if mode == "push":
        uid = str(cfg.get("user_id", "")).strip()
        if not uid or uid.startswith("請"):
            raise ValueError("push 模式需要有效 user_id（U 開頭）")
    elif mode == "multicast":
        ids = _collect_user_ids(cfg)
        if not ids:
            raise ValueError("multicast 模式需要 user_id 或 user_ids 列表")

    if not cfg.get("enabled", True):
        raise SystemExit("line_config.enabled=false，略過推播。")

    cfg["send_mode"] = mode
    return cfg


def _collect_user_ids(cfg: dict[str, Any]) -> list[str]:
    ids: list[str] = []
    primary = str(cfg.get("user_id", "")).strip()
    if primary and primary.startswith("U"):
        ids.append(primary)
    extra = cfg.get("user_ids") or []
    if isinstance(extra, list):
        for x in extra:
            s = str(x).strip()
            if s.startswith("U") and s not in ids:
                ids.append(s)
    return ids


def load_portfolio() -> dict[str, Any]:
    if not PORTFOLIO_JSON.exists():
        raise FileNotFoundError(
            f"找不到 {PORTFOLIO_JSON}\n"
            f"請先執行：python backtest_2.py"
        )
    with open(PORTFOLIO_JSON, "r", encoding="utf-8") as f:
        return json.load(f)


def _chunk_text(text: str) -> list[str]:
    chunks: list[str] = []
    remaining = text.strip()
    while remaining:
        chunks.append(remaining[:MAX_LINE_CHARS])
        remaining = remaining[MAX_LINE_CHARS:]
    return chunks or [""]


def _post_line(url: str, token: str, payload: dict) -> None:
    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json",
    }
    resp = requests.post(url, headers=headers, json=payload, timeout=30)
    if resp.status_code >= 300:
        raise RuntimeError(
            f"LINE API 失敗 HTTP {resp.status_code}: {resp.text[:400]}"
        )


def send_line_message(cfg: dict[str, Any], text: str) -> None:
    """依 send_mode 推播：push / multicast / broadcast。"""
    token = str(cfg["channel_access_token"]).strip()
    mode = cfg.get("send_mode", "push")
    chunks = _chunk_text(text)

    for i, chunk in enumerate(chunks, 1):
        messages = [{"type": "text", "text": chunk}]
        if mode == "broadcast":
            _post_line(LINE_BROADCAST_URL, token, {"messages": messages})
            _log(f"broadcast 第 {i}/{len(chunks)} 則（所有好友）")
        elif mode == "multicast":
            ids = _collect_user_ids(cfg)
            # LINE multicast 一次最多 500 人
            for start in range(0, len(ids), 500):
                batch = ids[start: start + 500]
                _post_line(
                    LINE_MULTICAST_URL, token,
                    {"to": batch, "messages": messages},
                )
            _log(f"multicast 第 {i}/{len(chunks)} 則（{len(ids)} 人）")
        else:
            uid = str(cfg["user_id"]).strip()
            _post_line(
                LINE_PUSH_URL, token,
                {"to": uid, "messages": messages},
            )
            _log(f"push 第 {i}/{len(chunks)} 則 → {uid[:8]}…")


# 相容舊錯誤處理呼叫
def send_line_text(token: str, user_id: str, text: str) -> None:
    send_line_message(
        {"channel_access_token": token, "user_id": user_id, "send_mode": "push"},
        text,
    )


def _fmt_pos_lines(rows: list[dict], empty: str = "  （無）") -> list[str]:
    if not rows:
        return [empty]
    out = []
    for r in rows:
        sig = "🚀" if r.get("sig_type") == "breakout" else "🟢"
        out.append(
            f"  {r['ticker']}  {r['industry']}\n"
            f"    入{r.get('entry_md', '?')}  "
            f"佔{r.get('alloc_pct', 0):.0%}  "
            f"損益{r.get('pnl', 0):+.1%}  "
            f"{r.get('bars_held', 0)}日 {sig}"
        )
    return out


def format_message(snap: dict[str, Any]) -> str:
    as_of = snap.get("as_of") or "—"
    gen = snap.get("generated_at") or dt.datetime.now().isoformat(timespec="seconds")
    n_held = snap.get("n_held", 0)
    max_pos = snap.get("max_positions", 10)
    new = snap.get("new") or []
    continued = snap.get("continued") or []
    removed = snap.get("removed") or []
    eq = snap.get("equity") or {}

    lines = [
        "🧠 回測持倉戰情摘要",
        f"📅 截至：{as_of}",
        f"🕒 產出：{gen}",
        f"持倉：{n_held} / {max_pos} 檔",
    ]
    if eq.get("total_ret") is not None:
        lines.append(f"截至目前獲利：{eq['total_ret']:+.1%}")
    elif eq.get("final") is not None and eq.get("init"):
        ret = float(eq["final"]) / float(eq["init"]) - 1.0
        lines.append(f"截至目前獲利：{ret:+.1%}")

    lines += ["", f"🆕 本日新增（{len(new)}）"]
    lines += _fmt_pos_lines(new)

    lines += ["", f"🔄 持續續抱（{len(continued)}）"]
    lines += _fmt_pos_lines(continued)

    lines += ["", f"❌ 今日剔除（{len(removed)}）"]
    if removed:
        for t in removed:
            lines.append(
                f"  {t['ticker']}  {t['industry']}\n"
                f"    入{t.get('entry_md','?')}→出{t.get('exit_md','?')}  "
                f"{t.get('pnl', 0):+.1%}  {t.get('reason', '')}"
            )
    else:
        lines.append("  （無）")

    lines += ["", "（來源：backtest_2 → latest_portfolio.json）"]
    return "\n".join(lines)


def run_backtest() -> None:
    _log("開始執行 backtest_2.py …")
    proc = subprocess.run(
        [sys.executable, str(ROOT / "backtest_2.py")],
        cwd=str(ROOT),
    )
    if proc.returncode != 0:
        raise RuntimeError(f"backtest_2.py 結束碼 {proc.returncode}")
    _log("回測完成。")


def is_weekday(d: dt.date | None = None) -> bool:
    d = d or dt.date.today()
    return d.weekday() < 5


def main() -> None:
    parser = argparse.ArgumentParser(description="推播回測持倉快照到 LINE")
    parser.add_argument("--dry-run", action="store_true", help="只印訊息不推播")
    parser.add_argument(
        "--run-backtest", action="store_true",
        help="先跑 backtest_2.py 再推播",
    )
    parser.add_argument(
        "--force", action="store_true",
        help="非平日也執行（搭配 --run-backtest 時略過週末跳過）",
    )
    args = parser.parse_args()

    if args.run_backtest:
        if not args.force and not is_weekday():
            _log("今日非平日，略過回測與推播。")
            return
        run_backtest()

    snap = load_portfolio()
    msg = format_message(snap)
    _log("--- 訊息預覽 ---\n" + msg + "\n---------------")

    if args.dry_run:
        _log("dry-run：不推播。")
        return

    cfg = load_config()
    send_line_message(cfg, msg)
    _log(f"完成（模式：{cfg.get('send_mode')}）。")


if __name__ == "__main__":
    try:
        main()
    except SystemExit:
        raise
    except Exception as exc:
        _log(f"ERROR: {exc}")
        try:
            cfg = json.loads(CONFIG_PATH.read_text(encoding="utf-8"))
            token = str(cfg.get("channel_access_token", "")).strip()
            uid = str(cfg.get("user_id", "")).strip()
            if token and uid and not uid.startswith("請"):
                send_line_text(
                    token, uid,
                    f"⚠️ line_alert 失敗\n{type(exc).__name__}: {exc}",
                )
        except Exception:
            pass
        sys.exit(1)
