import streamlit as st
import json
import pandas as pd
from datetime import datetime, timedelta
from github import Github

# ---------------- 設定與 GitHub 連線設定 ---------------- #
# 網頁基本設定
st.set_page_config(page_title="孩子生活管理存款系統", layout="wide")

# 檢查是否有設定 Secrets
if "GITHUB_TOKEN" not in st.secrets or "REPO_NAME" not in st.secrets:
    st.error("請先在 Streamlit Cloud 後台設定 Secrets：GITHUB_TOKEN 與 REPO_NAME")
    st.stop()

GITHUB_TOKEN = st.secrets["GITHUB_TOKEN"]
REPO_NAME = st.secrets["REPO_NAME"]  # 格式如 "你的帳號/你的儲存庫"
DATA_FILE = "kids_bank_data.json"

@st.cache_resource
def get_repo():
    g = Github(GITHUB_TOKEN)
    return g.get_repo(REPO_NAME)

def load_data():
    try:
        repo = get_repo()
        contents = repo.get_contents(DATA_FILE)
        data = json.loads(contents.decoded_content.decode("utf-8"))
        return data, contents.sha
    except Exception as e:
        st.error(f"讀取 GitHub 資料失敗：{e}")
        st.stop()

def save_data(data, sha):
    try:
        repo = get_repo()
        updated_content = json.dumps(data, ensure_ascii=False, indent=4)
        res = repo.update_file(
            path=DATA_FILE,
            message="Update via Streamlit",
            content=updated_content,
            sha=sha
        )
        return res['commit'].sha
    except Exception as e:
        st.error(f"寫回 GitHub 失敗：{e}")
        return sha

# 初始化 Session State
if 'data' not in st.session_state:
    data, sha = load_data()
    st.session_state['data'] = data
    st.session_state['sha'] = sha
    st.session_state['children'] = list(data['users'].keys())

# ---------------- 核心邏輯 (沿用原版並微調) ---------------- #
def auto_update_records(data):
    today = datetime.now().date()
    now = datetime.now()
    daily_reward = data.get('daily_reward', 0)
    updated = False
    
    for child_name, info in data['users'].items():
        existing_reward_dates = set()
        for r in info['history']:
            if r['type'] == '系統-每日獎勵':
                existing_reward_dates.add(r['date'][:10])
                
        existing_interest_months = set()
        for r in info['history']:
            if r['type'] == '系統-每月利息':
                existing_interest_months.add(r['date'][:7])
                
        open_date_str = info.get('open_date', data.get('last_update', today.strftime("%Y-%m-%d")))
        open_date = datetime.strptime(open_date_str, "%Y-%m-%d").date()
        start_date = open_date
        
        if now.hour > 22 or (now.hour == 22 and now.minute >= 30):
            end_date = today
        else:
            end_date = today - timedelta(days=1)
            
        new_records = []
        current_date = start_date
        while current_date <= end_date:
            date_key = current_date.strftime("%Y-%m-%d")
            month_key = current_date.strftime("%Y-%m")
            
            if current_date.day == 1 and month_key not in existing_interest_months:
                rate_pct = f"{info['rate']*100:.2f}".rstrip('0').rstrip('.')
                new_records.append({
                    "date": date_key + " 08:00", "type": "系統-每月利息",
                    "amount": 0, "note": f"利率 {rate_pct}%", "_is_interest": True
                })
            
            if daily_reward > 0 and date_key not in existing_reward_dates:
                new_records.append({
                    "date": date_key + " 22:30", "type": "系統-每日獎勵",
                    "amount": daily_reward, "note": "每日固定配給 (22:30發放)"
                })
            current_date += timedelta(days=1)
            
        if not new_records:
            continue
            
        for rec in new_records:
            rec['balance'] = 0
            info['history'].append(rec)
            
        info['history'].sort(key=lambda r: r['date'])
        
        current_balance = 0.0
        for record in info['history']:
            if record.get('_is_interest', False):
                interest = round(current_balance * info["rate"])
                if interest > 0:
                    record['amount'] = interest
                else:
                    record['_remove'] = True
                if '_is_interest' in record:
                    del record['_is_interest']
            current_balance += record['amount']
            record['balance'] = round(current_balance)
            
        info['history'] = [r for r in info['history'] if not r.get('_remove')]
        
        current_balance = 0.0
        for record in info['history']:
            current_balance += record['amount']
            record['balance'] = round(current_balance)
        info['balance'] = round(current_balance)
        updated = True
        
    if updated:
        data['last_update'] = today.strftime("%Y-%m-%d")
        return True
    return False

# 每次重新整理網頁時，檢查是否需要自動發獎勵/利息
if auto_update_records(st.session_state['data']):
    new_sha = save_data(st.session_state['data'], st.session_state['sha'])
    st.session_state['sha'] = new_sha
    st.toast("已自動補齊漏掉的每日獎勵與利息！")

# ---------------- UI 介面設計 ---------------- #
st.title("💰 孩子生活管理存款系統")

tab1, tab2, tab3, tab4 = st.tabs(["查看存款簿", "新增交易", "系統設定", "開戶日期"])

# --- Tab 1: 查看存款簿 ---
with tab1:
    col1, col2 = st.columns([1, 1])
    with col1:
        target = st.selectbox("檢視帳戶", st.session_state['children'])
    
    user_data = st.session_state['data']['users'][target]
    rate_display = f"{user_data['rate']*100:.2f}".rstrip('0').rstrip('.')
    st.markdown(f"### 目前餘額: **{int(round(user_data['balance']))}** 元 (當前利率: {rate_display}%)")
    
    if user_data['history']:
        df = pd.DataFrame(user_data['history'])
        df = df[['date', 'type', 'amount', 'balance', 'note']] # 重新排序欄位
        df.columns = ['日期時間', '類型', '異動金額', '目前結餘', '備註說明']
        # 反轉順序讓最新的在最上面
        st.dataframe(df.iloc[::-1], use_container_width=True, hide_index=True)
    else:
        st.info("目前尚無交易紀錄。")

# --- Tab 2: 新增交易 ---
with tab2:
    st.subheader("新增一筆交易")
    with st.form("transaction_form"):
        t_target = st.selectbox("選擇對象", st.session_state['children'] + ["兩人同時"])
        t_type = st.selectbox("交易類型", ["額外獎勵 (存入)", "懲罰扣款 (扣除)", "帳戶提取 (領出)"])
        t_amount = st.number_input("金額", min_value=0.0, step=10.0)
        t_note = st.text_input("備註 (選填)")
        
        submitted = st.form_submit_button("送出紀錄")
        if submitted:
            act_amount = float(t_amount)
            t_type_short = t_type.split(" ")[0]
            if t_type_short in ["懲罰扣款", "帳戶提取"]:
                act_amount = -abs(act_amount)
            
            selected_children = st.session_state['children'] if t_target == "兩人同時" else [t_target]
            today_str = datetime.now().strftime("%Y-%m-%d %H:%M")
            
            for child in selected_children:
                user = st.session_state['data']['users'][child]
                user['balance'] += act_amount
                user['history'].append({
                    "date": today_str, "type": t_type_short, "amount": act_amount,
                    "balance": round(user["balance"]), "note": t_note
                })
            
            new_sha = save_data(st.session_state['data'], st.session_state['sha'])
            st.session_state['sha'] = new_sha
            st.success("✅ 紀錄已成功寫回 GitHub！")
            st.rerun()

# --- Tab 3: 系統設定 ---
with tab3:
    st.subheader("系統參數設定")
    with st.form("settings_form"):
        daily_reward = st.number_input("每日固定發放獎勵 (元)", 
                                       value=float(st.session_state['data'].get('daily_reward', 0)))
        
        rates = {}
        for child in st.session_state['children']:
            current_rate = st.session_state['data']['users'][child]['rate'] * 100
            rates[child] = st.number_input(f"{child} 的存款利率 (%)", value=float(current_rate), format="%.2f")
            
        if st.form_submit_button("儲存設定"):
            st.session_state['data']['daily_reward'] = daily_reward
            for child in st.session_state['children']:
                st.session_state['data']['users'][child]['rate'] = round(rates[child] / 100, 4)
            
            new_sha = save_data(st.session_state['data'], st.session_state['sha'])
            st.session_state['sha'] = new_sha
            st.success("✅ 設定已更新並寫回 GitHub！")

# --- Tab 4: 開戶日期 ---
with tab4:
    st.subheader("設定各帳戶開戶日期")
    with st.form("open_date_form"):
        dates = {}
        for child in st.session_state['children']:
            current_date = st.session_state['data']['users'][child].get('open_date', datetime.now().strftime("%Y-%m-%d"))
            dates[child] = st.text_input(f"{child} 開戶日期 (YYYY-MM-DD)", value=current_date)
            
        if st.form_submit_button("儲存日期"):
            for child in st.session_state['children']:
                st.session_state['data']['users'][child]['open_date'] = dates[child]
            new_sha = save_data(st.session_state['data'], st.session_state['sha'])
            st.session_state['sha'] = new_sha
            st.success("✅ 開戶日期已更新！")