import streamlit as st
import pandas as pd
import requests
from requests.auth import HTTPBasicAuth
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry
from bs4 import BeautifulSoup
import google.generativeai as genai
import time
import re

# --- 基本設定 ---
st.set_page_config(page_title="プロ仕様 SEO メタジェネレーター", layout="wide")

def apply_custom_css():
    # Chrome等のブラウザ自動翻訳を強制無効化するmetaタグとCSS
    st.markdown("""
        <meta name="google" content="notranslate">
        <style>
        html, body, [class*="css"] {
            -webkit-font-smoothing: antialiased;
        }
        .report-table { width: 100%; border-collapse: collapse; font-size: 14px; table-layout: fixed; }
        .report-table th { background-color: #007bff; color: white; padding: 12px; text-align: left; }
        .report-table td { border: 1px solid #ddd; padding: 12px; vertical-align: top; word-wrap: break-word; white-space: normal; }
        .report-table tr:nth-child(even) { background-color: #f9f9f9; }
        .copy-btn { 
            margin-top: 8px; padding: 5px 10px; cursor: pointer; 
            background: #28a745; color: white; border: none; border-radius: 3px; font-size: 12px;
        }
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
    """利用可能な最新モデルを安全に自動取得"""
    try:
        genai.configure(api_key=api_key)
        available_models = [m.name for m in genai.list_models() if 'generateContent' in m.supported_generation_methods]
        
        priority = [
            "models/gemini-3.8-flash",
            "models/gemini-2.5-flash",
            "models/gemini-1.5-flash",
            "models/gemini-pro"
        ]
        for p in priority:
            if p in available_models:
                return genai.GenerativeModel(p)
                
        for m in available_models:
            if "flash" in m:
                return genai.GenerativeModel(m)
                
        return genai.GenerativeModel(available_models[0]) if available_models else None
    except Exception as e:
        st.error(f"モデル取得エラー: {e}")
        return None

def scrape_page(url, session, auth):
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/128.0.0.0 Safari/537.36",
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        "Accept-Language": "ja,en-US;q=0.9,en;q=0.8"
    }
    
    # ルート1: Jina AI Reader（最も安定してテキスト化可能）
    try:
        jina_url = f"https://r.jina.ai/{url}"
        res = requests.get(jina_url, timeout=5)
        if res.status_code == 200 and len(res.text) > 50:
            lines = [l.strip() for l in res.text.splitlines() if l.strip()]
            title = lines[0].replace("Title:", "").strip() if lines else "ページ情報"
            body = " ".join(lines[1:])[:1000]
            return title, body
    except Exception:
        pass

    # ルート2: 通常直接アクセス (タイムアウト極小3秒)
    try:
        res = session.get(url, headers=headers, auth=auth, timeout=(2, 3))
        if res.status_code == 200:
            res.encoding = 'utf-8'
            soup = BeautifulSoup(res.text, 'html.parser')
            title = (soup.title.string or "ページ情報").strip()
            for s in soup(["script", "style", "nav", "footer", "header"]): s.decompose()
            body = soup.get_text(separator=' ', strip=True)[:1000]
            return title, body
    except Exception:
        pass

    # ルート3: AllOrigins
    try:
        proxy_url = f"https://api.allorigins.win/raw?url={requests.utils.quote(url)}"
        res = requests.get(proxy_url, timeout=5)
        if res.status_code == 200:
            res.encoding = 'utf-8'
            soup = BeautifulSoup(res.text, 'html.parser')
            title = (soup.title.string or "ページ情報").strip()
            for s in soup(["script", "style", "nav", "footer", "header"]): s.decompose()
            body = soup.get_text(separator=' ', strip=True)[:1000]
            return title, body
    except Exception:
        pass

    # 取得失敗時はURLのパス自体をヒントとして渡すフォールバック
    return "URL解析モード", f"対象URL: {url} のページ内容に基づくディスクリプションを推測生成してください。"

def generate_meta_with_retry(model, url, title, body, company, max_retries=3):
    prompt = f"""SEOプロとして、以下の内容から120〜145文字の日本語meta descriptionを作成してください。
・社名は「{company}」で統一。
・最後は句点「。」で完結。
・本文のみ出力し、注釈や文字数カウントは一切含めない。
URL: {url} / タイトル: {title} / 内容: {body}"""

    for attempt in range(max_retries):
        try:
            response = model.generate_content(prompt)
            text = response.text.strip()
            return re.sub(r'[\(（].*?文字[\)）]', '', text).strip()
        except Exception as e:
            err_str = str(e)
            if "429" in err_str:
                wait_time = 16
                match = re.search(r'seconds:\s*(\d+)', err_str)
                if match:
                    wait_time = int(match.group(1)) + 2
                time.sleep(wait_time)
            elif attempt == max_retries - 1:
                return f"AI生成エラー: {err_str}"
            else:
                time.sleep(2)
    return "AI生成エラー: 待機上限を超過しました。"

# --- 3. メインアプリ実行 ---

if login_check():
    apply_custom_css()
    st.title("🚀 プロ仕様 SEO メタジェネレーター")

    with st.sidebar:
        st.header("⚙️ 設定")
        api_key = st.secrets.get("GEMINI_API_KEY") or st.text_input("Gemini API Key", type="password")
        st.divider()
        target_company = st.text_input(
            "社名の指定", 
            value="マイマイシーサー",
            help="指定した社名でディスクリプションを作成します。"
        )
        st.divider()
        st.header("🔒 認証")
        b_user = st.text_input("Basic User")
        b_pw = st.text_input("Basic PW", type="password")
        
        st.markdown("<br><br>", unsafe_allow_html=True)
        st.divider()
        if st.button("🚪 ログアウト", use_container_width=True):
            del st.session_state["password_correct"]
            st.rerun()

    uploaded_file = st.file_uploader("URLリストをアップロード (.xml または .txt)", type=["xml", "txt"])

    if uploaded_file and api_key:
        model = get_best_model(api_key)
        urls = []

        if uploaded_file.name.endswith(".xml"):
            soup_sitemap = BeautifulSoup(uploaded_file, 'xml')
            urls = [loc.text.strip() for loc in soup_sitemap.find_all('loc')]
        elif uploaded_file.name.endswith(".txt"):
            raw_text = uploaded_file.read().decode("utf-8", errors="ignore")
            urls = [line.strip() for line in raw_text.splitlines() if line.strip().startswith("http")]

        if urls and model:
            st.info(f"{len(urls)} 件のURLを検出しました。")
            
            if st.button("一括生成を開始"):
                auth = HTTPBasicAuth(b_user, b_pw) if b_user and b_pw else None
                results = []
                session = requests.Session()
                
                with st.status("SEOディスクリプションを生成中...", expanded=True) as status:
                    final_company = target_company if target_company else "貴社"
                    progress_bar = st.progress(0)
                    
                    for i, url in enumerate(urls):
                        try:
                            # タイムアウト等で止まらない高速フェッチ
                            t, b = scrape_page(url, session, auth)
                            desc = generate_meta_with_retry(model, url, t, b, final_company)
                            res = {"URL": url, "タイトル": t, "結果": desc, "文字数": len(desc)}
                        except Exception as e:
                            res = {"URL": url, "タイトル": "処理エラー", "結果": str(e), "文字数": 0}

                        results.append(res)
                        progress_bar.progress((i + 1) / len(urls))
                        st.write(f"生成完了 ({i+1}/{len(urls)}): {url}")
                        
                        # 複数件ある場合のみレート制限（5回/分）対策で待機
                        if i < len(urls) - 1:
                            time.sleep(13)
                
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
                            <button class="copy-btn" onclick="copyText('desc-{idx}', this)">コピー</button>
                        </td>
                        <td style="text-align:center;">{r['文字数']}</td>
                    </tr>"""

                full_html = f"""
                <html translate="no"><head><meta charset='UTF-8'><meta name="google" content="notranslate">
                <title>SEO Meta Report</title>
                <style>
                    body {{ font-family: sans-serif; padding: 30px; color: #333; }}
                    table {{ width: 100%; border-collapse: collapse; margin-top: 20px; table-layout: fixed; }}
                    th {{ background: #007bff; color: white; padding: 12px; text-align: left; }}
                    td {{ border: 1px solid #ddd; padding: 12px; vertical-align: top; word-wrap: break-word; }}
                    tr:nth-child(even) {{ background-color: #f9f9f9; }}
                    .copy-btn {{ 
                        margin-top: 8px; padding: 5px 10px; cursor: pointer; 
                        background: #28a745; color: white; border: none; border-radius: 3px; font-size: 12px;
                    }}
                    a {{ color: #007bff; text-decoration: none; }}
                </style>
                <script>
                    function copyText(id, btn) {{
                        var text = document.getElementById(id).innerText;
                        navigator.clipboard.writeText(text).then(function() {{
                            var original = btn.innerText;
                            btn.innerText = "✅ コピー完了";
                            btn.style.background = "#6c757d";
                            setTimeout(function() {{ 
                                btn.innerText = original; 
                                btn.style.background = "#28a745";
                            }}, 2000);
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
