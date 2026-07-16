# Streamlit Cloud / GitHub 部署說明
# 入口檔：app_2.py

## 目標

把戰情室部署成公開網址，例如：
`https://xxxxx.streamlit.app`

之後 LINE 圖文選單可改成「連結」打開此網址。

---

## 事前準備

1. 有 GitHub 帳號  
2. 本機已安裝 Git（或用 Cursor / GitHub Desktop）  
3. 確認 **不要** 把 `data/line_config.json` 推上 GitHub（已在 `.gitignore`）

---

## 步驟 A：推上 GitHub

### A-1. 在 GitHub 新建空倉庫

1. 開啟 https://github.com/new  
2. Repository name：`market_monitor_TW`  
3. 選 **Private**（建議，避免標的池被公開爬）  
4. **不要**勾選 README / .gitignore（專案已有）  
5. Create repository  

### A-2. 本機推送（在專案資料夾 PowerShell）

```powershell
cd C:\Users\Ray\Desktop\market_monitor_TW
# 路徑改成你實際位置

git init
git add .
git status
# 確認 data/line_config.json 沒有被加入

git commit -m "Deploy Streamlit war room app_2"
git branch -M main
git remote add origin https://github.com/<你的帳號>/market_monitor_TW.git
git push -u origin main
```

若 `net_buy_shares.csv` 太大推不上去（超過 100MB）：

```powershell
# 暫時不要上傳大 CSV（雲端會用「量能近似」或之後再補）
# 確認 .gitignore 已包含（見下方）
git rm --cached data/net_buy_shares.csv
git commit -m "Skip large net_buy csv for cloud"
git push
```

雲端沒有 CSV 時，網站仍可開，只是 NBR 會退回量能近似。

---

## 步驟 B：Streamlit Community Cloud 部署

1. 開啟 https://share.streamlit.io/ （或 https://streamlit.io/cloud）  
2. 用 **GitHub 帳號登入**  
3. **New app** / Create app  
4. 填寫：

| 欄位 | 填什麼 |
|------|--------|
| Repository | `你的帳號/market_monitor_TW` |
| Branch | `main` |
| Main file path | `app_2.py` |
| App URL（可選） | 例如 `tw-alpha-warroom` |

5. Deploy  
6. 等 2–10 分鐘建置完成  
7. 點開得到 `https://xxxx.streamlit.app`

---

## 步驟 C：第一次開啟注意

- 第一次會抓很多台股日線，**可能要等數分鐘**，畫面會轉圈。  
- 若逾時：在 Streamlit Cloud → Manage app → Reboot，再開一次。  
- 成功後把網址存起來，之後可給 LINE 選單當「連結」。

---

## 步驟 D：（可選）補法人 CSV 到雲端

若 CSV 不太大（建議 < 50MB），可提交：

```powershell
git add data/net_buy_shares.csv
git commit -m "Add net buy history for NBR"
git push
```

Streamlit Cloud 會自動重新部署。

---

## 常見問題

| 問題 | 處理 |
|------|------|
| App 一直 Booting / Error | 看 Cloud 右下 Logs；多半是依賴或記憶體 |
| yfinance 抓不到 | 雲端限流，稍後 Reboot 重試 |
| 沒有 NBR | 補上 `data/net_buy_shares.csv` 再 push |
| 不想公開程式 | GitHub 用 Private；Streamlit Cloud 支援 private repo |

---

## 本機仍可開發

```powershell
streamlit run app_2.py
```

雲端與本機互不干擾。LINE 08:30 排程仍在本機跑，與網站部署無關。
