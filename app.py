import streamlit as st
import pandas as pd
import requests
from requests.auth import HTTPBasicAuth
from bs4 import BeautifulSoup
import google.generativeai as genai
import time
import re

# --- 基本設定 ---
st.set_page_config(page_title="プロ仕様 SEO Meta Generator", layout="wide")

# --- 1. ログインチェック機能 ---
def check_password():
    """パスワードが正しいかチェックする。"""
    target_password = st.secrets.get("APP_PASSWORD", "admin123")

    if "password_correct" not in st.session_state:
        st.title("🚀 プロ仕様 SEO Meta Description 生成アプリ")
        st.subheader("🔒 社内専用ツール：ログインが必要です")
        
        password = st.text_input("アクセスパスワードを入力してください", type="password")
        if st.button("ログイン"):
            if password == target_password:
                st.session_state["password_correct"] = True
                st.rerun()
            else:
                st.error("パスワードが違います。管理者へお問い合わせください。")
        return False
    else:
        return True

# ログインしていない場合はここで停止
if not check_password():
    st.stop()

# --- ログイン成功後：メインアプリ画面 ---

st.title("🚀 プロ仕様 SEO Meta Description 生成アプリ")
st.caption("社内専用ツール：ログイン済み")

# --- サイドバー設定 ---
with st.sidebar:
    st.header("⚙️ 設定")
    # APIキー設定
    api_key = st.secrets.get("GEMINI_API_KEY") or st.text_input("Gemini API Keyを入力", type="password")
    
    st.divider()
    
    # 会社情報
    st.header("🏢 会社情報")
    target_company = st.text_input(
        "会社名・ブランド名（任意）", 
        placeholder="例：株式会社サンプル",
        help="ここに入力すると、AIが全ページでこの名称を正確に使用します。"
    )

    st.divider()
    
    # ベーシック認証セクション
    st.header("🔒 ベーシック認証")
    st.caption("テストサイト等の認証情報")
    basic_user = st.text_input("ユーザー名", key="basic_user_input")
    basic_pw = st.text_input("パスワード", type="password", key="basic_pw_input")
    
    # --- ログアウトボタンを一番下へ配置 ---
    st.markdown("<br><br><br>", unsafe_allow_html=True) # 余白を追加
    st.divider()
    if st.button("🚪 アプリからログアウト", use_container_width=True):
        del st.session_state["password_correct"]
        st.rerun()

# --- 関数定義 ---

def parse_sitemap(xml_content):
    try:
        soup = BeautifulSoup(xml_content, 'xml')
        return [loc.text for loc in soup.find_all('loc')]
    except Exception: return []

def scrape_page_content(url, user=None, pw=None):
    headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/140.0.0.0 Safari/537.36"}
    auth = HTTPBasicAuth(user, pw) if user and pw else None
    try:
        res = requests.get(url, headers=headers, auth=auth, timeout=15)
        res.encoding = res.apparent_encoding
        if res.status_code == 401: return "認証失敗", "ID/PWが違います"
        if res.status_code != 200: return "取得失敗", f"HTTP {res.status_code}"
        soup = BeautifulSoup(res.text, 'html.parser')
        title = soup.title.string if soup.title else "タイトルなし"
        for s in soup(["script", "style", "nav", "footer", "header"]): s.decompose()
        body = soup.get_text(separator=' ', strip=True)[:1500]
        return title, body
    except Exception as e: return "取得失敗", str(e)

def get_best_model_name(api_key):
    try:
        genai.configure(api_key=api_key)
        available_models = [m.name for m in genai.list_models() if 'generateContent' in m.supported_generation_methods]
        priorities = ["models/gemini-1.5-flash", "models/gemini-pro"]
        for p in priorities:
            if p in available_models: return p
        return available_models[0] if available_models else "models/gemini-1.5-flash"
    except Exception: return "models/gemini-1.5-flash"

def generate_description(api_key, model_name, url, title, body, company):
    try:
        genai.configure(api_key=api_key)
        model = genai.GenerativeModel(model_name)
        c_rule = f"・社名は「{company}」で統一すること。" if company else ""
        prompt = f"""SEOのプロとして、以下のページのmeta descriptionを120〜145文字程度の日本語で作成してください。最後は句点「。」で終わらせ、注釈は一切含めないこと。{c_rule}
        URL: {url} / タイトル: {title} / 内容: {body}"""
        response = model.generate_content(prompt)
        text = response.text.strip()
        text = re.sub(r'[\(（].*?文字[\)）]', '', text)
        return text
    except Exception as e: return f"エラー: {str(e)}"

# --- メイン処理 ---
uploaded_file = st.file_uploader("sitemap.xml をアップロード", type="xml")

if uploaded_file and api_key:
    urls = parse_sitemap(uploaded_file)
    if urls:
        st.success(f"{len(urls)} 件のURLを読み込みました。")
        best_model = get_best_model_name(api_key)
        
        if st.button("全ページの生成を開始する"):
            results = []
            progress_bar = st.progress(0)
            
            for i, url in enumerate(urls):
                title, body = scrape_page_content(url, basic_user, basic_pw)
                if title not in ["取得失敗", "認証失敗"]:
                    desc = generate_description(api_key, best_model, url, title, body, target_company)
                else:
                    desc = f"読み込めませんでした: {body}"
                
                char_count = len(desc) if "読み込めませんでした" not in desc else 0
                results.append({"URL": url, "タイトル": title, "生成結果": desc, "文字数": char_count})
                progress_bar.progress((i + 1) / len(urls))
                time.sleep(1)
            
            st.success("✅ 全ページの処理が完了しました！")
            
            df = pd.DataFrame(results)
            st.dataframe(df, column_config={"URL": st.column_config.LinkColumn("URL")}, hide_index=True, use_container_width=True)
            
            st.divider()
            st.write("### 📋 コピペ用リスト")
            for i, res in enumerate(results):
                with st.container(border=True):
                    st.markdown(f"**[{i+1}] {res['タイトル']}**")
                    st.code(res['生成結果'], language=None)
            
            # --- HTMLレポート作成 ---
            html_rows = ""
            for idx, r in enumerate(results):
                html_rows += f"""
                <tr>
                    <td><a href="{r['URL']}" target="_blank">{r['URL']}</a></td>
                    <td>{r['タイトル']}</td>
                    <td>
                        <span id="desc-{idx}">{r['生成結果']}</span>
                        <br>
                        <button class="copy-btn" onclick="copyText('desc-{idx}', this)">コピー</button>
                    </td>
                    <td style="text-align:center;">{r['文字数']}</td>
                </tr>
                """
            
            full_html = f"""
            <html><head><meta charset='UTF-8'>
            <title>SEO Meta Report</title>
            <style>
                body {{ font-family: sans-serif; padding: 30px; color: #333; }}
                table {{ width: 100%; border-collapse: collapse; margin-top: 20px; table-layout: fixed; }}
                th {{ background: #007bff; color: white; padding: 12px; text-align: left; }}
                td {{ border: 1px solid #ddd; padding: 12px; vertical-align: top; word-wrap: break-word; }}
                tr:nth-child(even) {{ background-color: #f9f9f9; }}
                .copy-btn {{ margin-top: 8px; padding: 5px 10px; cursor: pointer; background: #28a745; color: white; border: none; border-radius: 3px; font-size: 12px; }}
                a {{ color: #007bff; text-decoration: none; }}
            </style>
            <script>
                function copyText(id, btn) {{
                    var text = document.getElementById(id).innerText;
                    navigator.clipboard.writeText(text).then(function() {{
                        btn.innerText = "✅ コピー完了！";
                        setTimeout(function() {{ btn.innerText = "コピー"; }}, 2000);
                    }});
                }}
            </script>
            </head><body>
                <h1>SEO Meta Description Report</h1>
                <table>
                    <tr><th style="width:20%;">URL</th><th style="width:20%;">タイトル</th><th style="width:50%;">生成結果</th><th style="width:10%;">文字数</th></tr>
                    {html_rows}
                </table>
            </body></html>
            """
            st.download_button("レポートを保存", full_html, "seo_meta_report.html", "text/html")
    else:
        st.error("URLが見つかりません。")
