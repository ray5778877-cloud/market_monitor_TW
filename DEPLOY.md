# Streamlit 公開部署（免圖文選單）

主程式：`app_2.py`

## 一鍵部署到 Streamlit Community Cloud（建議）

1. 把本專案推到 **GitHub**（公開或私人皆可）
2. 開啟 https://share.streamlit.io/ （用 GitHub 登入）
3. **New app** → 選這個 repo
4. 設定：
   - **Main file path**：`app_2.py`
   - **Python version**：3.11 或 3.12
5. Deploy → 得到類似 `https://xxxx.streamlit.app` 的公開網址

之後把網址貼到 LINE 官方帳號簡介／自動回覆即可，**不必做圖文選單**。

## 注意

- `data/line_config.json` **不要**上傳（已在 `.gitignore`）
- `data/net_buy_shares.csv` 會一同上傳，雲端才能用 NBR 籌碼大腦
- 雲端第一次載入可能較慢（yfinance 下載）
