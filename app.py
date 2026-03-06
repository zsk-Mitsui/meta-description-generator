import streamlit as st
import pandas as pd
import requests
from requests.auth import HTTPBasicAuth
from bs4 import BeautifulSoup
import google.generativeai as genai
import time
import re
from concurrent.futures import ThreadPoolExecutor, as_completed

# --- 基本設定 ---
st.set_page_config(page_title="Advanced SEO Meta Generator", layout="wide")

# --- 1. ログイン認証 ---
def check_password():
    target_password = st.secrets.get("APP_PASSWORD", "admin123")
    if "password_correct" not in st.session_state:
        st.title("🚀 プロ仕様 SEO Meta Description 生成アプリ")
        st.subheader("🔒 セキュリティ認証")
        password = st.text_input("アクセスパスワード", type="password")
        if st.button("ログイン"):
            if password == target_password:
                st.session_state["password_correct"] = True
                st.rerun()
            else:
                st.error("パスワードが正しくありません。")
        return False
    return True

if not check_password():
    st.stop()

# --- 2. ユーティリティ関数 ---

def parse_sitemap(xml_content):
    """サイトマップからURLを高速に抽出"""
    try:
        soup = BeautifulSoup(xml_content, 'xml')
        return [loc.text.strip() for loc in soup.find_all('loc')]
    except Exception as e:
        st.error(f"サイトマップ解析エラー: {e}")
        return []

def get_ai_model(api_key):
    """利用可能な最適なモデルを自動選択"""
    try:
        genai.configure(api_key=api_key)
        # Gemini 1.5 Flashは高速かつSEOタスクに最適
        return genai.GenerativeModel("gemini-1.5-flash")
    except Exception as e:
        st.error(f"AIモデル設定エラー: {e}")
        return None

# --- 3. コア処理（スクレイピング & 生成） ---

def process_single_url(url, session, model, auth, company_name):
    """
    1つのURLに対して取得と生成を行う（スレッド並列実行用）
    """
    result = {"URL": url, "タイトル": "取得失敗", "生成結果": "", "文字数": 0, "ステータス": "⏳"}
    
    # --- スクレイピング ---
    try:
        headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"}
        response = session.get(url, headers=headers, auth=auth, timeout=15)
        response.encoding = response.apparent_encoding
        
        if response.status_code == 200:
            soup = BeautifulSoup(response.text, 'html.parser')
            title = soup.title.string.strip() if soup.title else "タイトルなし"
            for s in soup(["script", "style", "nav", "footer", "header"]):
                s.decompose()
            body = soup.get_text(separator=' ', strip=True)[:1200]
            result["タイトル"] = title
        else:
            result["生成結果"] = f"取得失敗 (HTTP {response.status_code})"
            result["ステータス"] = "❌"
            return result
    except Exception as e:
        result["生成結果"] = f"取得エラー: {str(e)}"
        result["ステータス"] = "❌"
        return result

    # --- AI生成 ---
    try:
        c_rule = f"・社名は必ず「{company_name}」とすること。" if company_name else ""
        prompt = f"""SEOライターとして、以下のページのmeta descriptionを120〜145文字の日本語で作成してください。
        最後は必ず句点で終わらせ、注釈は一切含めないこと。{c_rule}
        URL: {url} / タイトル: {title} / 内容: {body}"""
        
        # 指数バックオフ的なリトライは簡易化し、直列実行
        response = model.generate_content(prompt)
        desc = re.sub(r'[\(（].*?文字[\)）]', '', response.text).strip()
        result["生成結果"] = desc
        result["文字数"] = len(desc)
        result["ステータス"] = "✅"
    except Exception as e:
        result["生成結果"] = f"AI生成エラー: {str(e)}"
        result["ステータス"] = "⚠️"
        
    return result

# --- 4. メインUI ---

st.title("🚀 プロ仕様 SEO Meta Generator")
st.caption("Advanced Refactored Version 2026")

with st.sidebar:
    st.header("⚙️ システム設定")
    api_key = st.secrets.get("GEMINI_API_KEY") or st.text_input("Gemini API Key", type="password")
    st.divider()
    target_company = st.text_input("会社名 (固定用)", placeholder="株式会社サンプル")
    st.divider()
    st.header("🔒 認証設定")
    b_user = st.text_input("Basic Auth User")
    b_pw = st.text_input("Basic Auth PW", type="password")
    st.divider()
    # 並列スレッド数の設定（API制限を考慮してデフォルト3〜5推奨）
    max_workers = st.slider("並列処理数 (スレッド)", 1, 10, 3)
    
    if st.button("🚪 ログアウト"):
        del st.session_state["password_correct"]
        st.rerun()

uploaded_file = st.file_uploader("sitemap.xml をアップロード", type="xml")

if uploaded_file and api_key:
    urls = parse_sitemap(uploaded_file)
    model = get_ai_model(api_key)
    
    if urls and model:
        st.success(f"{len(urls)} 件のURLを検出。")
        
        if st.button("一括生成を開始"):
            results = []
            auth = HTTPBasicAuth(b_user, b_pw) if b_user and b_pw else None
            
            # 進行状況の可視化
            with st.status("SEO解析および生成を実行中...", expanded=True) as status:
                with requests.Session() as session:
                    # ThreadPoolExecutorによる並列実行
                    with ThreadPoolExecutor(max_workers=max_workers) as executor:
                        future_to_url = {executor.submit(process_single_url, url, session, model, auth, target_company): url for url in urls}
                        
                        progress_bar = st.progress(0)
                        processed_count = 0
                        
                        for future in as_completed(future_to_url):
                            res = future.result()
                            results.append(res)
                            processed_count += 1
                            progress_bar.progress(processed_count / len(urls))
                            st.write(f"{res['ステータス']} {res['URL']}")
                
                status.update(label="✅ 全ページの処理が完了しました！", state="complete", expanded=False)

            # --- 結果表示と出力 ---
            df = pd.DataFrame(results)
            st.write("### 📊 生成結果一覧")
            st.dataframe(df, column_config={"URL": st.column_config.LinkColumn("URL")}, hide_index=True, use_container_width=True)
            
            # コピペ用リスト
            st.divider()
            st.write("### 📋 クイックコピー")
            for i, r in enumerate(results):
                if r['ステータス'] == "✅":
                    with st.container(border=True):
                        st.markdown(f"**{r['タイトル']}**")
                        st.code(r['生成結果'], language=None)

            # HTMLレポート生成
            html_rows = "".join([f"<tr><td><a href='{r['URL']}'>{r['URL']}</a></td><td>{r['タイトル']}</td><td>{r['生成結果']}</td><td>{r['文字数']}</td></tr>" for r in results])
            full_html = f"<html><head><meta charset='UTF-8'><style>body{{font-family:sans-serif;padding:20px;}} table{{width:100%;border-collapse:collapse;font-size:14px;}} th{{background:#007bff;color:white;padding:10px;text-align:left;}} td{{border:1px solid #ddd;padding:10px;}}</style></head><body><h1>SEO Report</h1><table><tr><th>URL</th><th>タイトル</th><th>生成結果</th><th>文字数</th></tr>{html_rows}</table></body></html>"
            st.download_button("レポートをダウンロード", full_html, "seo_report.html", "text/html")
