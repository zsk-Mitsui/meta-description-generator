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
st.set_page_config(page_title="Professional SEO Meta Generator", layout="wide")

# --- カスタムCSS（横スクロール防止 & レスポンシブ調整） ---
def apply_custom_css():
    st.markdown("""
        <style>
        .report-table { width: 100%; border-collapse: collapse; font-size: 14px; table-layout: fixed; }
        .report-table th { background-color: #007bff; color: white; padding: 12px; text-align: left; }
        .report-table td { border: 1px solid #ddd; padding: 12px; vertical-align: top; word-wrap: break-word; white-space: normal; }
        .report-table tr:nth-child(even) { background-color: #f9f9f9; }
        </style>
    """, unsafe_allow_html=True)

# --- 1. ログイン認証 ---
def login_check():
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
                st.error("パスワードが正しくありません。")
        return False
    return True

# --- 2. 通信・AI処理関数 ---

def get_best_model(api_key):
    """APIから利用可能なモデルを動的に取得して404を回避"""
    try:
        genai.configure(api_key=api_key)
        models = [m.name for m in genai.list_models() if 'generateContent' in m.supported_generation_methods]
        priority = ["models/gemini-1.5-flash", "models/gemini-1.5-pro", "models/gemini-pro"]
        for p in priority:
            if p in models: return genai.GenerativeModel(p)
        return genai.GenerativeModel(models[0]) if models else None
    except Exception as e:
        st.error(f"モデル取得エラー: {e}")
        return None

def scrape_page(url, session, auth):
    headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36"}
    try:
        res = session.get(url, headers=headers, auth=auth, timeout=15)
        res.encoding = res.apparent_encoding
        if res.status_code != 200: return "取得失敗", f"HTTP {res.status_code}"
        soup = BeautifulSoup(res.text, 'html.parser')
        title = soup.title.string.strip() if soup.title else "タイトルなし"
        # 不要タグ除去
        for s in soup(["script", "style", "nav", "footer", "header"]): s.decompose()
        body = soup.get_text(separator=' ', strip=True)[:1500]
        return title, body
    except Exception as e:
        return "取得失敗", str(e)

def generate_meta(model, url, title, body, company):
    try:
        prompt = f"""SEOプロフェッショナルとして、以下の内容から120〜145文字の日本語meta descriptionを作成してください。
        ・社名は必ず「{company}」と表記すること。
        ・最後は必ず句点「。」で完結。
        ・解説、文字数カウント、括弧書きは一切含めず、本文のみ出力せよ。
        URL: {url} / タイトル: {title} / 内容: {body}"""
        response = model.generate_content(prompt)
        text = response.text.strip()
        # AI特有の注釈を除去
        clean_text = re.sub(r'[\(（].*?文字[\)）]', '', text).strip()
        return clean_text
    except Exception as e:
        return f"AI生成エラー: {str(e)}"

# --- 3. メインアプリ実行 ---

if login_check():
    apply_custom_css()
    st.title("🚀 プロ仕様 SEO Meta Generator")
    st.caption("Parallel High-Speed Mode / ログイン済み")

    with st.sidebar:
        st.header("⚙️ 設定")
        api_key = st.secrets.get("GEMINI_API_KEY") or st.text_input("Gemini API Key", type="password")
        st.divider()
        target_company = st.text_input("社名の固定 (空欄ならAIが自動判定)", placeholder="例：株式会社サンプル")
        st.divider()
        st.header("🔒 認証")
        b_user = st.text_input("Basic User")
        b_pw = st.text_input("Basic PW", type="password")
        
        st.markdown("<br><br>", unsafe_allow_html=True)
        st.divider()
        if st.button("🚪 アプリからログアウト", use_container_width=True):
            del st.session_state["password_correct"]
            st.rerun()

    uploaded_file = st.file_uploader("sitemap.xml をアップロード", type="xml")

    if uploaded_file and api_key:
        model = get_best_model(api_key)
        # サイトマップからURL抽出
        soup_sitemap = BeautifulSoup(uploaded_file, 'xml')
        urls = [loc.text.strip() for loc in soup_sitemap.find_all('loc')]
        
        if urls and model:
            st.info(f"{len(urls)} 件のURLを検出しました。")
            
            if st.button("全ページ一括生成を開始"):
                auth = HTTPBasicAuth(b_user, b_pw) if b_user and b_pw else None
                results = []
                
                with st.status("SEO解析および並列生成を実行中...", expanded=True) as status:
                    with requests.Session() as session:
                        # 会社名の自動特定
                        final_company = target_company
                        if not final_company:
                            st.write("🔍 サイトから正式な会社名を特定しています...")
                            t, b = scrape_page(urls[0], session, auth)
                            try:
                                res_name = model.generate_content(f"以下から正式社名のみ抽出せよ：{t} {b}")
                                final_company = res_name.text.strip()
                                st.write(f"✅ 社名を「{final_company}」に統一します。")
                            except: final_company = "貴社"

                        # ThreadPoolExecutorによる並列実行（5並列）
                        st.write("🚀 各ページのディスクリプションを並列生成中...")
                        progress_bar = st.progress(0)
                        
                        def process_task(url):
                            t, b = scrape_page(url, session, auth)
                            if t == "取得失敗": return {"URL": url, "タイトル": t, "結果": b, "文字数": 0}
                            desc = generate_meta(model, url, t, b, final_company)
                            return {"URL": url, "タイトル": t, "結果": desc, "文字数": len(desc)}

                        with ThreadPoolExecutor(max_workers=5) as executor:
                            future_to_url = {executor.submit(process_task, url): url for url in urls}
                            for i, future in enumerate(as_completed(future_to_url)):
                                res = future.result()
                                results.append(res)
                                progress_bar.progress((i + 1) / len(urls))
                
                status.update(label="✨ すべての処理が完了しました！", state="complete", expanded=False)

                # --- 結果表示 ---
                st.write("### 📋 生成結果サマリー")
                html_table = "<table class='report-table'><tr><th style='width:25%'>URL</th><th style='width:20%'>タイトル</th><th style='width:45%'>生成結果</th><th style='width:10%'>文字数</th></tr>"
                for r in results:
                    html_table += f"<tr><td><a href='{r['URL']}' target='_blank'>{r['URL']}</a></td><td>{r['タイトル']}</td><td>{r['結果']}</td><td>{r['文字数']}</td></tr>"
                html_table += "</table>"
                st.write(html_table, unsafe_allow_html=True)

                # クイックコピーセクション
                st.divider()
                st.write("### 📑 クイックコピー")
                for r in results:
                    if r['文字数'] > 0:
                        with st.container(border=True):
                            st.markdown(f"**{r['タイトル']}**")
                            st.code(r['結果
