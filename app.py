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

# --- カスタムCSS（横スクロール防止 & デザイン調整） ---
st.markdown("""
    <style>
    .report-table { width: 100%; border-collapse: collapse; font-size: 14px; table-layout: fixed; }
    .report-table th { background-color: #007bff; color: white; padding: 12px; text-align: left; }
    .report-table td { border: 1px solid #ddd; padding: 12px; vertical-align: top; word-wrap: break-word; white-space: normal; }
    .report-table tr:nth-child(even) { background-color: #f9f9f9; }
    .copy-btn { background: #28a745; color: white; border: none; border-radius: 3px; padding: 4px 8px; cursor: pointer; font-size: 11px; margin-top: 5px; }
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

# --- 2. ユーティリティ関数 ---

def scrape_page(url, session, auth):
    """ページの内容を抽出"""
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
    except Exception as e:
        return "取得失敗", str(e)

def extract_company_name(model, url, title, body):
    """【新機能】1件目の内容から正式な会社名を特定する"""
    prompt = f"以下のページ内容から、このサイトを運営している正式な会社名（またはブランド名）を1つだけ抽出してください。株式会社等の付随情報も正確に抜き出してください。余計な解説は不要。社名のみ出力せよ。\nURL: {url}\nタイトル: {title}\n本文: {body}"
    try:
        response = model.generate_content(prompt)
        return response.text.strip()
    except:
        return ""

def generate_meta(model, url, title, body, company):
    """メタディスクリプション生成"""
    try:
        prompt = f"""SEOプロライターとして、以下のページのmeta descriptionを120〜145文字の日本語で作成。
        ・社名は必ず「{company}」と表記。
        ・最後は必ず句点「。」で完結。
        ・注釈や文字数カウントは一切含めない。
        URL: {url} / タイトル: {title} / 内容: {body}"""
        response = model.generate_content(prompt)
        text = response.text.strip()
        return re.sub(r'[\(（].*?文字[\)）]', '', text).strip()
    except Exception as e:
        return f"AIエラー: {e}"

# --- 3. メイン処理 ---

with st.sidebar:
    st.header("⚙️ 設定")
    api_key = st.secrets.get("GEMINI_API_KEY") or st.text_input("Gemini API Key", type="password")
    st.divider()
    target_company = st.text_input("正式社名の指定 (空欄ならAIが自動判定)", placeholder="株式会社サンプル")
    st.divider()
    st.header("🔒 認証")
    b_user = st.text_input("User")
    b_pw = st.text_input("PW", type="password")
    max_workers = st.slider("同時処理数", 1, 10, 5)
    
    if st.button("🚪 ログアウト"):
        del st.session_state["password_correct"]
        st.rerun()

uploaded_file = st.file_uploader("sitemap.xml をアップロード", type="xml")

if uploaded_file and api_key:
    genai.configure(api_key=api_key)
    model = genai.GenerativeModel("gemini-1.5-flash")
    
    soup = BeautifulSoup(uploaded_file, 'xml')
    urls = [loc.text.strip() for loc in soup.find_all('loc')]
    
    if urls:
        st.info(f"{len(urls)} 件のURLを検出しました。")
        
        if st.button("生成を開始する"):
            auth = HTTPBasicAuth(b_user, b_pw) if b_user and b_pw else None
            results = []
            
            with st.status("SEO解析実行中...", expanded=True) as status:
                with requests.Session() as session:
                    # 1. 会社名の自動特定（未入力時）
                    final_company = target_company
                    if not final_company:
                        st.write("🔍 サイト名から正式な会社名を特定中...")
                        first_title, first_body = scrape_page(urls[0], session, auth)
                        final_company = extract_company_name(model, urls[0], first_title, first_body)
                        st.write(f"✅ 社名を「{final_company}」に統一して生成します。")

                    # 2. 並列処理
                    st.write("🚀 各ページの生成を開始...")
                    progress_bar = st.progress(0)
                    
                    def task(url):
                        t, b = scrape_page(url, session, auth)
                        if t == "取得失敗":
                            return {"URL": url, "タイトル": t, "結果": b, "文字数": 0}
                        desc = generate_meta(model, url, t, b, final_company)
                        return {"URL": url, "タイトル": t, "結果": desc, "文字数": len(desc)}

                    with ThreadPoolExecutor(max_workers=max_workers) as executor:
                        future_to_url = {executor.submit(task, url): url for url in urls}
                        for i, future in enumerate(as_completed(future_to_url)):
                            res = future.result()
                            results.append(res)
                            progress_bar.progress((i + 1) / len(urls))
                
                status.update(label="✨ 全件完了！", state="complete", expanded=False)

            # --- 結果表示（横スクロールなしテーブル） ---
            st.write("### 📋 生成結果サマリー")
            
            html_table = "<table class='report-table'><tr><th style='width:25%'>URL</th><th style='width:20%'>タイトル</th><th style='width:45%'>生成結果</th><th style='width:10%'>文字数</th></tr>"
            for r in results:
                html_table += f"<tr><td><a href='{r['URL']}' target='_blank'>{r['URL']}</a></td><td>{r['タイトル']}</td><td>{r['結果']}</td><td>{r['文字数']}</td></tr>"
            html_table += "</table>"
            
            st.write(html_table, unsafe_allow_html=True)

            # --- クイックコピーセクション ---
            st.divider()
            st.write("### 📑 クイックコピー")
            for r in results:
                with st.container(border=True):
                    st.markdown(f"**{r['タイトル']}**")
                    st.code(r['結果'], language=None)

            # ダウンロードボタン
            full_html = f"<html><head><meta charset='UTF-8'></head><body><h1>SEO Report</h1>{html_table}</body></html>"
            st.download_button("レポートを保存", full_html, "seo_report.html", "text/html")
