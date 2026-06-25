# 🏦 孩子生活管理存款系統（Streamlit + Google Sheets）

由原本的 tkinter 桌面版改寫，部署到 **GitHub + Streamlit Community Cloud**，手機瀏覽器即可操作。
資料存在 **Google Sheets**，App 休眠或重新部署都不會遺失。

---

## 一、檔案結構

```
your-repo/
├── streamlit_app.py        # 主程式（雲端找這個檔當進入點，檔名勿改）
├── requirements.txt
├── secrets.toml.example    # secrets 範本（真正內容不要上傳）
├── .gitignore
└── README.md
```

兩種儲存模式會自動切換：

| 情況 | 使用的儲存 |
|---|---|
| 有設定好 `gcp_service_account` + `spreadsheet`（雲端） | ☁️ Google Sheets（持久保存） |
| 沒設定 secrets（本機測試） | 💾 本機 `kids_bank_data.json` |

左側欄上方會顯示目前是哪一種，方便確認有沒有接上。

---

## 二、設定 Google Sheets（一次性，約 10 分鐘）

### 1. 建立服務帳號與金鑰
1. 到 https://console.cloud.google.com 建立或選一個專案。
2.「API 和服務 → 程式庫」啟用 **Google Sheets API** 與 **Google Drive API**。
3.「API 和服務 → 憑證 → 建立憑證 → 服務帳號」，建好後進入該帳號 →「金鑰 → 新增金鑰 → JSON」，下載一個 JSON 檔。

### 2. 建立試算表並分享給服務帳號
1. 新建一個 Google 試算表（空白即可，程式會自動建立名為 `data` 的工作表）。
2. 複製試算表網址中 `/d/` 與 `/edit` 之間那段 ID。
3. 按「共用」，把 JSON 裡的 `client_email`（像 `xxx@xxx.iam.gserviceaccount.com`）加為**編輯者**。
   👉 沒做這步會出現 403 權限錯誤。

### 3. 填 secrets
參考 `secrets.toml.example`，把下載的 JSON 各欄位填進去，並填上試算表 ID。

- **Streamlit Cloud**：App → ⋮ → **Settings → Secrets**，整段貼上、Save。
- **本機測試**：在專案下建立 `.streamlit/secrets.toml`（已被 `.gitignore` 排除）。

> `private_key` 欄位務必用三個雙引號 `"""..."""` 包起來，並保留裡面的 `\n`。

---

## 三、部署

1. 把上面檔案推上 GitHub repo。
2. https://share.streamlit.io → New app → 選 repo、分支、主檔 `streamlit_app.py` → Deploy。
3. 到 Settings → Secrets 貼上金鑰，App 會自動重啟。
4. 手機開網址 →「加入主畫面」，即像一個 App。

### 本機測試
```bash
pip install -r requirements.txt
streamlit run streamlit_app.py
```
（不放 secrets 就用本機檔模式；要測 Sheets 就放 `.streamlit/secrets.toml`。）

---

## 四、資料怎麼存的

整包資料（沿用原本的巢狀結構）以 JSON 字串寫進 `data` 工作表的 A 欄。
單一儲存格上限 5 萬字元，超過時程式會自動分段存到 A1、A2、A3…，讀取時再串接還原。
側邊欄保留「下載備份 / 上傳還原 (JSON)」，可隨時手動存一份保險。

> 試算表內看到的是一整串 JSON、不是漂亮表格；要看人類可讀版本，用「📥 匯出 Excel」即可。

---

## 五、與桌面版的差異

| 桌面版 (tkinter) | 雲端版 (Streamlit) |
|---|---|
| `messagebox` 彈窗 | `st.success / st.error / st.toast` |
| `filedialog` 選檔 | 瀏覽器下載鈕 / 上傳元件 |
| `root.after` 每 30 秒定時發獎勵 | **開啟 App 時自動補發**（雲端無常駐背景程式） |
| Treeview 右鍵編輯/刪除 | 表格 + 「編輯/刪除」展開區 |
| 本機 JSON 檔 | Google Sheets（本機測試時退回 JSON 檔） |

每日獎勵（22:30）與每月利息（1 日 08:00）的計算邏輯**完全保留**：當天有人打開 App 就會一次補齊先前漏掉的部分。

---

## 六、改寫時修正的問題

1. **定時發獎勵的時間判斷錯誤（真實 bug）**：原 `schedule_daily_reward` 用
   `if now.hour >= 22 and now.minute >= 30:`，在 **23:00–23:29** 會誤判成「還沒到」而不發。
   雲端版改用「開啟即補發」，採用正確判斷 `now.hour > 22 or (now.hour == 22 and now.minute >= 30)`，bug 消失。
2. **存檔強化**：本機模式原子寫入；Sheets 模式先 `clear` 再整段寫入。
3. **金額驗證**：送出交易要求金額大於 0，避免誤存 0 元空紀錄。

> 已用測試驗證：分段儲存→串接還原無誤、補發筆數正確、結餘連貫、重複開啟不重複加錢、Excel 匯出再匯入筆數一致、資料損壞會自動處理。

---

## 七、注意事項

- Google Sheets API 免費額度約每分鐘 60 次讀取。本程式每次互動讀一次，家庭用量綽綽有餘；若短時間瘋狂點擊出現 `429`，稍候即可。
- 多裝置同時操作時，以「最後存檔者」為準（家庭情境通常沒問題）。
