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
st.set_page_config(page_title="Ultra SEO Meta Generator", layout="wide")

# カスタムCSS：横スクロールを防止し、文章を枠内で適切に改行
st.markdown("""
    <style>
    .report-table { width: 100%; border-collapse: collapse; font-size: 14px; table-layout: fixed; }
    .report-table th { background-color: #007bff; color: white; padding: 12px; text-align: left; }
    .report-table td { border: 1px solid #ddd; padding: 12px; vertical-align: top; word-wrap: break-word; white-space: normal; }
    .report-table tr:nth-child(even) { background-color: #f9f9f9; }
    </style>
""", unsafe_allow_html=True)

# --- 1. ログイン認証 ---
def check_password():
    target_password = st.secrets.get("APP_PASSWORD", "admin123")
    if "password_correct" not in st.session_state:
        st.title("🚀 プロ仕様 SEO Meta Description 生成アプリ")
        st.subheader("🔒 社内専用ログイン")
        password = st.text_input("アクセスパスワード", type="password")
        if st.button("ログイン"):
            if password == target_password:
                st.session_state["password_correct"] = True
                st.rerun()
            else:
                st.error("パスワードが違います。")
        return False
    return True

if not check_password():
    st.stop()

# --- 2. 処理関数群 ---

def scrape_page(url, session, auth):
    headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36"}
    try:
        res = session.get(url, headers=headers, auth=auth, timeout=15)
        res.encoding = res.apparent_encoding
        if res.status_code != 200: return "取得失敗", f"HTTP {res.status_code}"
        soup = BeautifulSoup(res.text, 'html.parser')
        title = soup.title.string.strip() if soup.title else "タイトルなし"
        for s in soup(["script", "style", "nav", "footer", "header"]): s.decompose()
        body = soup.get_text(separator=' ', strip=True)[:1500]
        return title, body
    except Exception as e: return "取得失敗", str(e)

def get_stable_model(api_key):
    """通信エラーを回避する安定したモデル呼び出し"""
    try:
        genai.configure(api_key=api_key)
        # バージョン不整合を避けるため、最も標準的なIDで初期化
        return genai.GenerativeModel('gemini-1.5-flash')
    except Exception as e:
        st.error(f"AIモデル初期化エラー: {e}")
        return None

def generate_meta(model, url, title, body, company):
    try:
        prompt = f"""SEO専門家として、以下の内容から120〜145文字の日本語meta descriptionを作成してください。
        ・社名は「{company}」で統一。
        ・最後は必ず「。」で完結。
        ・解説や文字数注釈は一切含めないこと。
        URL: {url} / タイトル: {title} / 内容: {body}"""
        response = model.generate_content(prompt)
        text = response.text.strip()
        return re.sub(r'[\(（].*?文字[\)）]', '', text).strip()
    except Exception as e:
        return f"AIエラー: {str(e)}"

# --- 3. メインUI ---

with st.sidebar:
    st.header("⚙️ 設定")
    api_key = st.secrets.get("GEMINI_API_KEY") or st.text_input("Gemini API Key", type="password")
    st.divider()
    target_company = st.text_input("社名の指定 (空欄ならAIが自動判定)", placeholder="株式会社サンプル")
    st.divider()
    st.header("🔒 認証")
    b_user = st.text_input("Basic Auth User")
    b_pw = st.text_input("Basic Auth PW", type="password")
    
    # ログアウトボタンを最下部へ
    st.markdown("<br><br>", unsafe_allow_html=True)
    st.divider()
    if st.button("🚪 アプリからログアウト", use_container_width=True):
        del st.session_state["password_correct"]
        st.rerun()

uploaded_file = st.file_uploader("sitemap.xml をアップロード", type="xml")

if uploaded_file and api_key:
    model = get_stable_model(api_key)
    urls = parse_sitemap_content := [loc.text.strip() for loc in BeautifulSoup(uploaded_file, 'xml').find_all('loc')]
    
    if urls and model:
        st.info(f"{len(urls)} 件のURLを検出しました。")
        
        if st.button("全ページの生成を開始する"):
            auth = HTTPBasicAuth(b_user, b_pw) if b_user and b_pw else None
            results = []
            # 並列処理数を5に固定してスライダーを削除
            MAX_WORKERS = 5
            
            with st.status("SEO解析および生成を実行中...", expanded=True) as status:
                with requests.Session() as session:
                    # 会社名の自動特定ロジック
                    final_company = target_company
                    if not final_company:
                        st.write("🔍 サイトから正式な会社名を特定しています...")
                        t, b = scrape_page(urls[0], session, auth)
                        prompt_name = f"以下の内容から正式な会社名のみを抽出せよ。解説不要。\nタイトル: {t}\n本文: {b}"
                        final_company = model.generate_content(prompt_name).text.strip()
                        st.write(f"✅ 社名を「{final_company}」に統一します。")

                    # 並列実行
                    st.write("🚀 各ページのディスクリプションを並列生成中...")
                    progress_bar = st.progress(0)
                    
                    def process_task(url):
                        t, b = scrape_page(url, session, auth)
                        if t == "取得失敗": return {"URL": url, "タイトル": t, "結果": b, "文字数": 0}
                        desc = generate_meta(model, url, t, b, final_company)
                        return {"URL": url, "タイトル": t, "結果": desc, "文字数": len(desc)}

                    with ThreadPoolExecutor(max_workers=MAX_WORKERS) as executor:
                        future_to_url = {executor.submit(process_task, url): url for url in urls}
                        for i, future in enumerate(as_completed(future_to_url)):
                            res = future.result()
                            results.append(res)
                            progress_bar.progress((i + 1) / len(urls))
                
                status.update(label="✨ すべての処理が完了しました！", state="complete", expanded=False)

            # --- 結果表示（横スクロールなしテーブル） ---
            st.write("### 📋 生成結果サマリー")
            html_table = "<table class='report-table'><tr><th style='width:25%'>URL</th><th style='width:20%'>タイトル</th><th style='width:45%'>生成結果</th><th style='width:10%'>文字数</th></tr>"
            for r in results:
                html_table += f"<tr><td><a href='{r['URL']}' target='_blank'>{r['URL']}</a></td><td>{r['タイトル']}</td><td>{r['結果']}</td><td>{r['文字数']}</td></tr>"
            html_table += "</table>"
            st.write(html_table, unsafe_allow_html=True)

            # クイックコピー
            st.divider()
            st.write("### 📑 クイックコピー")
            for r in results:
                if r['文字数'] > 0:
                    with st.container(border=True):
                        st.markdown(f"**{r['タイトル']}**")
                        st.code(r['結果'], language=None)

            # レポート保存
            full_html = f"<html><head><meta charset='UTF-8'></head><body><h1>SEO Report</h1>{html_table}</body></html>"
            st.download_button("レポートを保存", full_html, "seo_report.html", "text/html")
