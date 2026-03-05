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

st.title("🚀 プロ仕様 SEO Meta Description 生成アプリ")
st.write("ベーシック認証対応・最新安定モデル(1.5-flash)使用版です。")

# --- サイドバー設定 ---
with st.sidebar:
    st.header("⚙️ 設定")
    # APIキー取得（Secretsを優先）
    api_key = st.secrets.get("GEMINI_API_KEY") or st.text_input("Gemini API Keyを入力", type="password")
    
    st.divider()
    target_company = st.text_input("会社名（任意）", placeholder="例：株式会社サンプル")

    st.divider()
    st.header("🔒 ベーシック認証")
    st.caption("テストサイト等の認証情報を入力してください")
    basic_user = st.text_input("ユーザー名", key="b_user")
    basic_pw = st.text_input("パスワード", type="password", key="b_pw")

# --- 関数定義 ---

def parse_sitemap(xml_content):
    try:
        soup = BeautifulSoup(xml_content, 'xml')
        urls = [loc.text for loc in soup.find_all('loc')]
        return urls
    except Exception as e:
        st.error(f"サイトマップ解析エラー: {e}")
        return []

def scrape_page_content(url, user=None, pw=None):
    headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/140.0.0.0 Safari/537.36"}
    auth = HTTPBasicAuth(user, pw) if user and pw else None
    
    try:
        res = requests.get(url, headers=headers, auth=auth, timeout=15)
        res.encoding = res.apparent_encoding
        
        if res.status_code == 401:
            return "認証失敗", "IDまたはパスワードが間違っています。"
        if res.status_code != 200:
            return "取得失敗", f"HTTPエラー: {res.status_code}"
        
        soup = BeautifulSoup(res.text, 'html.parser')
        title = soup.title.string if soup.title else "タイトルなし"
        for s in soup(["script", "style", "nav", "footer", "header"]):
            s.decompose()
        body = soup.get_text(separator=' ', strip=True)[:1500]
        return title, body
    except Exception as e:
        return "取得失敗", str(e)

def generate_description(api_key, url, title, body, company):
    try:
        genai.configure(api_key=api_key)
        # 確実に存在する安定版モデル「gemini-1.5-flash」を使用
        model = genai.GenerativeModel("gemini-1.5-flash")
        
        c_rule = f"・社名は必ず「{company}」と表記すること。" if company else ""
        prompt = f"""
        あなたはSEO専門家です。以下の内容から、120〜150文字のmeta descriptionを日本語で作成してください。
        最後は必ず句点「。」で完結させ、余計な注釈や文字数カウントは一切含めないでください。
        {c_rule}
        
        URL: {url}
        タイトル: {title}
        内容: {body}
        """
        
        response = model.generate_content(prompt)
        # 余計なカッコ書きなどを除去
        clean_text = re.sub(r'[\(（]\d+文字[\)）]', '', response.text).strip()
        return clean_text
    except Exception as e:
        return f"AIエラー: {str(e)}"

# --- メイン処理 ---

uploaded_file = st.file_uploader("sitemap.xml をアップロード", type="xml")

if uploaded_file and api_key:
    urls = parse_sitemap(uploaded_file)
    if urls:
        st.info(f"URLを {len(urls)} 件検出しました。")
        
        if st.button("生成を開始する"):
            results = []
            progress_bar = st.progress(0)
            status_text = st.empty()
            
            for i, url in enumerate(urls):
                status_text.write(f"⏳ 処理中 ({i+1}/{len(urls)}): {url}")
                
                # ページ取得
                title, body = scrape_page_content(url, basic_user, basic_pw)
                
                # 生成
                if title not in ["取得失敗", "認証失敗"]:
                    desc = generate_description(api_key, url, title, body, target_company)
                else:
                    desc = f"読み込み不可: {body}"
                
                # レポート用にリンク化
                linked_url = f'<a href="{url}" target="_blank">{url}</a>'
                
                results.append({
                    "URL": linked_url,
                    "タイトル": title,
                    "生成ディスクリプション": desc,
                    "文字数": len(desc) if "エラー" not in desc else 0
                })
                
                progress_bar.progress((i + 1) / len(urls))
                time.sleep(1) # API制限回避
            
            status_text.success("✅ 全ページの処理が完了しました！")
            df = pd.DataFrame(results)
            
            # 画面表示
            st.write("### 生成結果一覧")
            st.write(df.to_html(escape=False, index=False), unsafe_allow_html=True)
            
            # HTMLレポート出力
            html_report = f"""
            <html><head><meta charset='UTF-8'><style>
                body {{ font-family: sans-serif; padding: 20px; }}
                table {{ border-collapse: collapse; width: 100%; }}
                th {{ background: #007bff; color: white; padding: 10px; text-align: left; }}
                td {{ padding: 10px; border-bottom: 1px solid #eee; font-size: 14px; }}
                a {{ color: #007bff; text-decoration: none; }}
            </style></head>
            <body>
                <h1>SEO Meta Description Report</h1>
                {df.to_html(escape=False, index=False)}
            </body></html>
            """
            st.download_button("レポートをHTMLで保存", html_report, "seo_report.html", "text/html")
    else:
        st.error("サイトマップからURLを抽出できませんでした。")
elif not api_key:
    st.warning("左側の設定でAPIキーを入力してください。")
