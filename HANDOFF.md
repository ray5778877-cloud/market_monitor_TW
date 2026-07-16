# market_monitor_TW — 新電腦交接手冊

給新電腦／新 Cursor Agent 快速接上。  
專案根目錄範例：`C:\Users\<帳號>\Desktop\market_monitor_TW`

---

## 一句話現況

台股 **Alpha Score v11.2（NBR 籌碼大腦）**：

- 行情：每次用 **yfinance** 抓日線（沒有本地股價 Excel）
- 法人：本地 `data/net_buy_shares.csv`（`fetch_net_buy.py` 產生）
- 戰情室：`streamlit run app_2.py`
- 回測：`python backtest_2.py` → 寫入 `data/latest_portfolio.json`
- LINE：`python line_alert.py` 讀快照推播（可 `broadcast` 給全部好友）
- 排程：平日 **08:30** 本機跑 `run_line_alert.bat`
- 機密：`data/line_config.json` 不要公開上傳

---

## 主要檔案

| 檔案 | 用途 |
|------|------|
| `app_2.py` | Streamlit 戰情室（請用這個，不要用舊的 `app.py`） |
| `backtest_2.py` | 歷史回測引擎（請用這個，不要用舊的 `backtest.py`） |
| `fetch_net_buy.py` | 爬三大法人，寫入 `data/net_buy_shares.csv` |
| `line_alert.py` | 讀取回測快照，推播 LINE |
| `run_line_alert.bat` | 排程用：先回測再推播 |
| `register_line_alert_task.ps1` | 註冊／更新 Windows 排程 |
| `requirements.txt` | Python 依賴 |
| `HANDOFF.md` | 本交接手冊 |

---

## 資料夾 `data/` 說明

| 檔案 | 必備？ | 說明 |
|------|--------|------|
| `net_buy_shares.csv` | 強烈建議 | 法人淨買超歷史。沒有會退回「成交量 Barra」，NBR 大腦不完整 |
| `line_config.json` | 要推 LINE 就必備 | token + user_id。從 `line_config.example.json` 複製改名 |
| `holdings.json` | 可選 | 網站「持倉診斷」記住的持股 |
| `latest_portfolio.json` | 推播前要有 | 由 `backtest_2.py` 自動產生 |
| `*.log` | 可選 | 執行紀錄，可刪 |

**沒有 Excel 股價庫。** 股價每次用 yfinance 下載；`data` 裡主要是法人 CSV，不是股價 Excel。

---

## 5. 回測資料時點（08:30 合不合理？）

**08:30 合理**，適合當「開盤前簡報」。

實際資料意義：

1. **股價（yfinance 日線）**  
   - 回測抓到「今天」為止的日線。  
   - 早上 08:30 時，**今天這根日K通常還沒有**（或未完成），所以持倉／信號本質是 **上一交易日收盤** 的結果。

2. **法人（net_buy_shares.csv）**  
   - 三大法人日報多在**盤後**才公布。  
   - 早上 08:30 能拿到的，一般是 **昨天或更早** 的法人買賣超，不是「今天即時法人」。

3. **結論**  
   - 08:30 = 開盤前複習「昨天收盤後的大腦結論」→ 適合。  
   - 若要「收盤後含今日法人」→ 改排 **14:00 之後**，且當天先跑過 `fetch_net_buy.py`。

---

## 6. 新電腦完整設定步驟

### 步驟 1：確認在專案目錄

```powershell
cd C:\Users\User\Desktop\market_monitor_TW
# 若路徑不同，改成你實際放置的位置
dir
```

應看得到 `app_2.py`、`backtest_2.py`、`line_alert.py`、`fetch_net_buy.py`、`data`。

### 步驟 2：確認 Python 可用

```powershell
python --version
python -c "import pandas, yfinance, requests, streamlit; print('deps OK')"
```

### 步驟 3：確認／補齊法人 CSV

```powershell
dir data\net_buy_shares.csv
```

若沒有或太舊：

```powershell
python fetch_net_buy.py --days 60
```

### 步驟 4：確認 LINE 設定

```powershell
notepad data\line_config.json
```

確認：

- `channel_access_token` 已填  
- `user_id` 是 **U 開頭**（不是 `@181teqqq`，那是 Bot ID）  
- `send_mode` 若要給所有好友：`"broadcast"`  
- `enabled`: `true`

### 步驟 5：先 dry-run 看訊息

```powershell
python line_alert.py --dry-run
```

若提示找不到 `latest_portfolio.json`，先：

```powershell
python backtest_2.py
python line_alert.py --dry-run
```

### 步驟 6：真的寄 LINE

```powershell
python line_alert.py
```

手機應收到持倉摘要。

### 步驟 7：註冊每天（平日）08:30

```powershell
Set-ExecutionPolicy -Scope Process Bypass -Force
.\register_line_alert_task.ps1
```

若顯示 `Register-ScheduledTask failed` 或 `存取被拒`：

1. 開始選單找 **Windows PowerShell**  
2. **右鍵 → 以系統管理員身分執行**  
3. 再執行上面兩行  

### 步驟 8：驗證排程

```powershell
Get-ScheduledTask -TaskName MarketMonitorTW_LineAlert_0830 | Format-List TaskName,State
```

手動觸發測試：

```powershell
Start-ScheduledTask -TaskName MarketMonitorTW_LineAlert_0830
```

---

## 9. 建議每日節奏

| 時間 | 動作 |
|------|------|
| 約 08:00（可選） | `python fetch_net_buy.py --days 10` 補最新法人 |
| **08:30（自動）** | 回測 + LINE 推播「昨收持倉／新增／續抱／剔除」 |
| 盤中（手動） | `streamlit run app_2.py` 看戰情室 |

---

## 10. 常見錯誤

| 錯誤 | 解法 |
|------|------|
| `register_line_alert_task.ps` 找不到 | 檔名應為 `.ps1` |
| `Register-ScheduledTask : 存取被拒` | 系統管理員開啟 PowerShell 再跑；或用已更新的 Limited 版腳本 |
| yfinance 大量 Failed download | 限流，稍後重試；不影響「已有快照只推播」 |
| 找不到 `latest_portfolio.json` | 先跑 `python backtest_2.py` |
| LINE HTTP 401 | token 錯誤或已撤銷，到 Developers 重新 Issue |

---

## 11. 給新電腦 Cursor Agent 的貼上用提示

把下面整段貼給新電腦的 Agent：

```
請先讀專案根目錄 HANDOFF.md。

這是台股 Alpha Score v11.2 NBR 專案：
- 行情：yfinance（無本地股價 Excel）
- 法人：data/net_buy_shares.csv（fetch_net_buy.py 產生）
- 戰情室：streamlit run app_2.py
- 回測：python backtest_2.py → 寫入 data/latest_portfolio.json
- LINE：python line_alert.py 讀快照推播；send_mode=broadcast 寄全部好友
- 排程：平日 08:30 本機跑 run_line_alert.bat（register_line_alert_task.ps1 註冊）
- 機密：data/line_config.json 不要 commit
```

---

*文件產生時機：移機交接用。若排程時間或 send_mode 有改，以實際 `register_line_alert_task.ps1` 與 `data/line_config.json` 為準。*
