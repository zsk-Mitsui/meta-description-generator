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

# カスタムCSS：横スクロールを防止し、文章を枠内で適切に改行
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

# --- 2. 処理関数群 ---

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
        res = session.get(url, headers=headers, auth=auth, timeout=12)
        res.encoding = res.apparent_encoding
        if res.status_code != 200: return "取得失敗", f"HTTP {res.status_code}"
        soup = BeautifulSoup(res.text, 'html.parser')
        title = (soup.title.string or "タイトルなし").strip()
        for s in soup(["script", "style", "nav", "footer", "header"]): s.decompose()
        body = soup.get_text(separator=' ', strip=True)[:1200]
        return title, body
    except Exception as e:
        return "取得失敗", str(e)

def generate_meta(model, url, title, body, company):
    try:
        time.sleep(0.2)
        prompt = f"""SEOプロとして、以下の内容から120〜145文字の日本語meta descriptionを作成してください。
        ・社名は「{company}」で統一。
        ・最後は句点「。」で完結。
        ・本文のみ出力し、注釈やカウントは含めない。
        URL: {url} / タイトル: {title} / 内容: {body}"""
        response = model.generate_content(prompt)
        text = response.text.strip()
        return re.sub(r'[\(（].*?文字[\)）]', '', text).strip()
    except Exception as e:
        return f"AI生成エラー: {str(e)}"

# --- 3. メインアプリ実行 ---

if login_check():
    apply_custom_css()
    st.title("🚀 プロ仕様 SEO Meta Generator")
    st.caption("XML Sitemap & TXT List Compatible / ログイン済み")

    with st.sidebar:
        st.header("⚙️ 設定")
        api_key = st.secrets.get("GEMINI_API_KEY") or st.text_input("Gemini API Key", type="password")
        st.divider()
        target_company = st.text_input(
            "社名の指定 (空欄ならAIが自動判定)", 
            placeholder="例：株式会社サンプル"
        )
        st.divider()
        st.header("🔒 認証")
        b_user = st.text_input("Basic User")
        b_pw = st.text_input("Basic PW", type="password")
        
        st.markdown("<br><br>", unsafe_allow_html=True)
        st.divider()
        if st.button("🚪 アプリからログアウト", use_container_width=True):
            del st.session_state["password_correct"]
            st.rerun()

    # 【修正】 typeに "txt" を追加
    uploaded_file = st.file_uploader("URLリストをアップロード (.xml または .txt)", type=["xml", "txt"])

    if uploaded_file and api_key:
        model = get_best_model(api_key)
        urls = []

        # --- ファイル形式に応じた解析 ---
        if uploaded_file.name.endswith(".xml"):
            # サイトマップ(XML)の解析
            soup_sitemap = BeautifulSoup(uploaded_file, 'xml')
            urls = [loc.text.strip() for loc in soup_sitemap.find_all('loc')]
        elif uploaded_file.name.endswith(".txt"):
            # テキストファイルの解析（1行1URL）
            raw_text = uploaded_file.read().decode("utf-8")
            # 改行で分割し、空行や前後のスペースを除去
            urls = [line.strip() for line in raw_text.splitlines() if line.strip().startswith("http")]

        if urls and model:
            st.info(f"{len(urls)} 件のURLを検出しました。")
            
            if st.button("全ページ一括生成を開始"):
                auth = HTTPBasicAuth(b_user, b_pw) if b_user and b_pw else None
                results = []
                
                with st.status("SEO解析および並列生成を実行中...", expanded=True) as status:
                    with requests.Session() as session:
                        final_company = target_company
                        if not final_company:
                            st.write("🔍 サイト情報を解析して社名を特定中...")
                            t, b = scrape_page(urls[0], session, auth)
                            try:
                                res_name = model.generate_content(f"以下から正式社名のみ抽出せよ：{t} {b}")
                                final_company = res_name.text.strip()
                                st.write(f"✅ 社名を「{final_company}」に決定しました。")
                            except: final_company = "貴社"

                        st.write("🚀 各ページのディスクリプションを生成中...")
                        progress_bar = st.progress(0)
                        
                        def process_task(url):
                            try:
                                t, b = scrape_page(url, session, auth)
                                if t == "取得失敗": return {"URL": url, "タイトル": t, "結果": b, "文字数": 0}
                                desc = generate_meta(model, url, t, b, final_company)
                                return {"URL": url, "タイトル": t, "結果": desc, "文字数": len(desc)}
                            except Exception as e:
                                return {"URL": url, "タイトル": "処理エラー", "結果": str(e), "文字数": 0}

                        with ThreadPoolExecutor(max_workers=3) as executor:
                            future_to_url = {executor.submit(process_task, url): url for url in urls}
                            for i, future in enumerate(as_completed(future_to_url)):
                                res = future.result()
                                results.append(res)
                                progress_bar.progress((i + 1) / len(urls))
                                st.write(f"完了 ({i+1}/{len(urls)}): {res['URL']}")
                
                status.update(label="✨ すべての処理が完了しました！", state="complete", expanded=False)

                # 結果表示
                st.write("### 📋 生成結果サマリー")
                html_table = "<table class='report-table'><tr><th style='width:25%'>URL</th><th style='width:20%'>タイトル</th><th style='width:45%'>生成結果</th><th style='width:10%'>文字数</th></tr>"
                for r in results:
                    html_table += f"<tr><td><a href='{r['URL']}' target='_blank'>{r['URL']}</a></td><td>{r['タイトル']}</td><td>{r['結果']}</td><td>{r['文字数']}</td></tr>"
                html_table += "</table>"
                st.write(html_table, unsafe_allow_html=True)

                st.divider()
                st.write("### 📑 クイックコピー (アプリ上)")
                for r in results:
                    if r['文字数'] > 0:
                        with st.container(border=True):
                            st.markdown(f"**{r['タイトル']}**")
                            st.code(r['結果'], language=None)

                # ダウンロード用HTML
                html_rows_dl = ""
                for idx, r in enumerate(results):
                    html_rows_dl += f"""
                    <tr>
                        <td><a href="{r['URL']}" target="_blank">{r['URL']}</a></td>
                        <td>{r['タイトル']}</td>
                        <td>
                            <span id="desc-{idx}">{r['結果']}</span><br>
                            <button class="copy-btn" onclick="copyText('desc-{idx}', this)" style="background:#28a745;color:white;border:none;border-radius:3px;padding:5px 10px;cursor:pointer;font-size:12px;margin-top:5px;">コピー</button>
                        </td>
                        <td style="text-align:center;">{r['文字数']}</td>
                    </tr>"""

                full_html = f"""
                <html><head><meta charset='UTF-8'>
                <style>
                    body {{ font-family: sans-serif; padding: 20px; color: #333; }}
                    table {{ width: 100%; border-collapse: collapse; margin-top: 20px; table-layout: fixed; }}
                    th {{ background: #007bff; color: white; padding: 12px; text-align: left; }}
                    td {{ border: 1px solid #ddd; padding: 12px; vertical-align: top; word-wrap: break-word; }}
                    tr:nth-child(even) {{ background-color: #f9f9f9; }}
                </style>
                <script>
                    function copyText(id, btn) {{
                        var text = document.getElementById(id).innerText;
                        navigator.clipboard.writeText(text).then(function() {{
                            btn.innerText = "✅ コピー完了";
                            setTimeout(function() {{ btn.innerText = "コピー"; }}, 2000);
                        }});
                    }}
                </script>
                </head><body>
                    <h1>SEO Meta Description Report</h1>
                    <table>
                        <tr><th style="width:20%;">URL</th><th style="width:20%;">タイトル</th><th style="width:50%;">生成結果</th><th style="width:10%;">文字数</th></tr>
                        {html_rows_dl}
                    </table>
                </body></html>"""
                
                st.download_button("レポート（HTML）を保存", full_html, "description_report.html", "text/html")
        else:
            st.error("ファイル内に有効なURLが見つかりませんでした。")
