#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
fetch_net_buy.py — 台股三大法人淨買賣超歷史爬蟲
================================================
從 TWSE（上市 T86）+ TPEx（上櫃）API 逐日爬取三大法人淨買超股數，
儲存至 data/net_buy_shares.csv，供 backtest_2.py / app_2.py 的 NBR 大腦使用。

使用方式：
  python fetch_net_buy.py              # 預設抓近 2 年
  python fetch_net_buy.py --days 60   # 最近 60 個日曆日（快速補齊近期）
  python fetch_net_buy.py --full      # 近 5 年完整歷史

特性：
  ✅ 增量更新：已爬取的日期自動跳過，只補缺漏
  ✅ 上市 + 上櫃合併（TWSE 資料優先；TPEx 補缺）
  ✅ 自動排除週末，非交易日 API 回空值時靜默跳過
  ✅ 限速 1 秒/次，避免被封鎖

輸出格式：
  data/net_buy_shares.csv
    index   = Date UTC (YYYY-MM-DD TZ=UTC)
    columns = 純數字股票代碼（如 "2330", "3105"）
    values  = 當日三大法人淨買超股數（買超為正，賣超為負）
"""

from __future__ import annotations

import argparse
import datetime as dt
import os
import sys
import time

import pandas as pd
import requests

# ─────────────────────────────────────────────────────────────────────────
# 設定
# ─────────────────────────────────────────────────────────────────────────
OUTPUT_DIR    = "data"
OUTPUT_CSV    = os.path.join(OUTPUT_DIR, "net_buy_shares.csv")
REQUEST_DELAY = 1.2    # 秒（兩個 API call 之間；保守值避免被 ban）
MAX_RETRIES   = 2
RETRY_SLEEP   = 1.5
# (connect_timeout, read_timeout) — 防止 TCP 層無限 hang
TIMEOUT       = (6, 18)

TWSE_URL = (
    "https://www.twse.com.tw/rwd/zh/fund/T86"
    "?response=json&date={date}&selectType=ALL"
)
TPEX_URL = (
    "https://www.tpex.org.tw/web/stock/3insti/daily_trade/"
    "3itrade_hedge_result.php?l=zh-tw&o=json&se=AL&d={roc_date}"
)
HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/120.0.0.0 Safari/537.36"
    )
}


# ─────────────────────────────────────────────────────────────────────────
# 爬取函式
# ─────────────────────────────────────────────────────────────────────────
def _get_session() -> requests.Session:
    """建立每次請求用的短生命週期 Session，避免殭屍連線殘留。"""
    s = requests.Session()
    s.headers.update(HEADERS)
    return s


def fetch_twse(date_str: str) -> dict[str, float]:
    """
    TWSE RWD T86（上市三大法人）。
    date_str: 'YYYYMMDD'  →  {股票代碼: 淨買超股數}
    row[18] = 三大法人買賣超股數合計（RWD 新版第 19 欄，索引 18）
    """
    url = TWSE_URL.format(date=date_str)
    for attempt in range(MAX_RETRIES):
        try:
            with _get_session() as s:
                resp = s.get(url, timeout=TIMEOUT)
            resp.raise_for_status()
            data = resp.json()
            if data.get("stat") != "OK":
                return {}
            result: dict[str, float] = {}
            for row in data.get("data", []):
                try:
                    code = str(row[0]).strip()
                    if not code.isdigit():
                        continue
                    net = float(str(row[18]).replace(",", ""))
                    result[code] = net
                except (ValueError, IndexError):
                    pass
            return result
        except Exception:
            if attempt < MAX_RETRIES - 1:
                time.sleep(RETRY_SLEEP)
    return {}


def fetch_tpex(date_str: str) -> dict[str, float]:
    """
    TPEx（上櫃三大法人）。
    date_str: 'YYYYMMDD'  →  {股票代碼: 淨買超股數}
    row[0] = 代號，row[23] = 三大法人合計買賣超股數（第 24 欄，索引 23）
    """
    try:
        d = dt.datetime.strptime(date_str, "%Y%m%d")
        roc_date = f"{d.year - 1911}/{d.month:02d}/{d.day:02d}"
    except ValueError:
        return {}

    url = TPEX_URL.format(roc_date=roc_date)
    for attempt in range(MAX_RETRIES):
        try:
            with _get_session() as s:
                resp = s.get(url, timeout=TIMEOUT)
            resp.raise_for_status()
            data = resp.json()
            result: dict[str, float] = {}
            for row in data.get("aaData", []):
                try:
                    code = str(row[0]).strip()
                    if not code.isdigit():
                        continue
                    net = float(str(row[23]).replace(",", ""))
                    result[code] = net
                except (ValueError, IndexError):
                    pass
            return result
        except Exception:
            if attempt < MAX_RETRIES - 1:
                time.sleep(RETRY_SLEEP)
    return {}


def fetch_day(date_str: str) -> dict[str, float]:
    """合併 TWSE（上市）+ TPEx（上櫃）當日三大法人資料，TWSE 優先。"""
    tpex = fetch_tpex(date_str)
    time.sleep(0.5)
    twse = fetch_twse(date_str)
    return {**tpex, **twse}   # TWSE 優先覆蓋 TPEx


# ─────────────────────────────────────────────────────────────────────────
# 工具函式
# ─────────────────────────────────────────────────────────────────────────
def get_weekday_dates(start: dt.date, end: dt.date) -> list[str]:
    """生成候選交易日清單（排除週末；台灣國定假日由 API 空回值自動過濾）。"""
    dates: list[str] = []
    cur = start
    while cur <= end:
        if cur.weekday() < 5:
            dates.append(cur.strftime("%Y%m%d"))
        cur += dt.timedelta(days=1)
    return dates


def load_existing() -> pd.DataFrame:
    """載入已存在的 CSV；不存在時回傳空 DataFrame。"""
    if not os.path.exists(OUTPUT_CSV):
        return pd.DataFrame()
    try:
        df = pd.read_csv(OUTPUT_CSV, index_col=0, parse_dates=True)
        df = df[df.index.notna()]          # 丟棄 NaT 殭屍列
        if df.index.tz is None:
            df.index = df.index.tz_localize("UTC")
        else:
            df.index = df.index.tz_convert("UTC")
        df = df.sort_index()
        return df
    except Exception as e:
        print(f"  ⚠️  讀取既有 CSV 失敗（{e}），將重新建立。")
        return pd.DataFrame()


def save(df: pd.DataFrame) -> None:
    """儲存 DataFrame 至 CSV，確保 data/ 目錄存在。"""
    os.makedirs(OUTPUT_DIR, exist_ok=True)
    df.to_csv(OUTPUT_CSV)


# ─────────────────────────────────────────────────────────────────────────
# 主程式
# ─────────────────────────────────────────────────────────────────────────
def main() -> None:
    parser = argparse.ArgumentParser(
        description="台股三大法人淨買超歷史爬蟲",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )
    group = parser.add_mutually_exclusive_group()
    group.add_argument("--days", type=int, metavar="N",
                       help="抓取最近 N 個日曆日（快速補缺；預設 730 天）")
    group.add_argument("--full", action="store_true",
                       help="抓取近 5 年完整歷史（首次爬取建議使用）")
    args = parser.parse_args()

    today = dt.date.today()
    if args.full:
        start = today - dt.timedelta(days=365 * 5)
        mode_str = "近 5 年完整歷史"
    elif args.days:
        start = today - dt.timedelta(days=args.days)
        mode_str = f"最近 {args.days} 個日曆日"
    else:
        start = today - dt.timedelta(days=730)
        mode_str = "近 2 年（預設）"

    SEP = "═" * 56
    print(f"\n{SEP}")
    print("  台股三大法人淨買超爬蟲  TWSE T86 + TPEx")
    print(f"  模式   : {mode_str}")
    print(f"  範圍   : {start} → {today}")
    print(f"  輸出   : {OUTPUT_CSV}")
    print(SEP)

    # ── 載入既有資料 ────────────────────────────────────────────────────
    print("\n[1/3] 載入既有資料...")
    existing_df = load_existing()
    if not existing_df.empty:
        existing_dates = {ts.strftime("%Y%m%d") for ts in existing_df.index if not pd.isnull(ts)}
        print(f"  既有：{len(existing_df)} 個交易日 × {existing_df.shape[1]} 檔股票")
    else:
        existing_dates = set()
        print("  既有：（無，首次建立）")

    # ── 決定待抓取日期 ───────────────────────────────────────────────────
    all_dates = get_weekday_dates(start, today)
    new_dates = [d for d in all_dates if d not in existing_dates]

    print(f"\n[2/3] 候選工作日：{len(all_dates)} 天  →  待抓取：{len(new_dates)} 天")
    if not new_dates:
        print("\n  ✅ 資料已是最新，無需更新！")
        print(f"\n{SEP}")
        print(
            "  ✅ 大腦與數據完全對齊修復！"
            "即可體驗 NBR 戰鬥機的極致威力！"
        )
        print(SEP + "\n")
        return

    # ── 逐日爬取 ─────────────────────────────────────────────────────────
    print(f"\n[3/3] 開始爬取（限速 {REQUEST_DELAY}s/日）...")
    print("      按 Ctrl+C 可中斷，已爬取部分將自動儲存。\n")

    rows: list[dict] = []
    skipped_count = 0
    fetched_count = 0

    try:
        for i, date_str in enumerate(new_dates, 1):
            bar_done  = int(30 * i / len(new_dates))
            bar_str   = "█" * bar_done + "░" * (30 - bar_done)
            sys.stdout.write(f"\r  [{bar_str}] {i}/{len(new_dates)}  {date_str}  ")
            sys.stdout.flush()

            day_data = fetch_day(date_str)

            if not day_data:
                skipped_count += 1
            else:
                fetched_count += 1
                d  = dt.datetime.strptime(date_str, "%Y%m%d")
                ts = pd.Timestamp(d.date(), tz="UTC")
                row: dict = {"__date__": ts}
                row.update(day_data)
                rows.append(row)

            time.sleep(REQUEST_DELAY)

            # 每 50 筆自動存檔（防意外中斷丟失）
            if rows and (i % 50 == 0):
                _interim_save(rows, existing_df)

    except KeyboardInterrupt:
        print("\n\n  ⚠️  使用者中斷，儲存已爬取資料...")

    print(f"\n\n  爬取完成：{fetched_count} 個交易日 / 跳過 {skipped_count} 個非交易日")

    # ── 儲存結果 ─────────────────────────────────────────────────────────
    if not rows:
        print("  無新資料寫入。")
        return

    combined = _build_combined(rows, existing_df)
    save(combined)

    print(f"\n  ✅ 已儲存：{OUTPUT_CSV}")
    print(f"  資料規模：{len(combined)} 個交易日 × {len(combined.columns)} 檔股票")
    print(f"  日期範圍：{combined.index[0].date()} → {combined.index[-1].date()}")
    print(f"\n{SEP}")
    print(
        "  ✅ 大腦與數據完全對齊修復！\n"
        "  現在可以執行：\n"
        "    streamlit run app_2.py     （即時戰情室）\n"
        "    python backtest_2.py       （歷史回測）"
    )
    print(SEP + "\n")


def _build_combined(rows: list[dict], existing_df: pd.DataFrame) -> pd.DataFrame:
    new_df = pd.DataFrame(rows).set_index("__date__").sort_index()
    if not existing_df.empty:
        combined = pd.concat([existing_df, new_df])
        combined = combined[~combined.index.duplicated(keep="last")].sort_index()
    else:
        combined = new_df
    return combined


def _interim_save(rows: list[dict], existing_df: pd.DataFrame) -> None:
    try:
        combined = _build_combined(rows, existing_df)
        save(combined)
    except Exception:
        pass


if __name__ == "__main__":
    main()
