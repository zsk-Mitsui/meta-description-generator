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
st.write("ボタンを押しても動かない場合は、エラーメッセージが表示されるのを待つか、APIキーを確認してください。")

# --- サイドバー設定 ---
with st.sidebar:
    st.header("⚙️ 設定確認")
    # APIキー取得
    api_key_input = st.secrets.get("GEMINI_API_KEY") or ""
    if not api_key_input:
        api_key_input = st.text_input("Gemini API Keyを入力", type="password")
    
    if api_key_input:
        st.success("✅ APIキーを認識しました")
    else:
        st.warning("⚠️ APIキーが必要です")

    st.divider()
    target_company = st.text_input("会社名（任意）", placeholder="例：株式会社サンプル")

    st.divider()
    st.header("🔒 ベーシック認証")
    basic_user = st.text_input("ユーザー名")
    basic_pw = st.text_input("パスワード", type="password")

# --- 関数定義 ---

def parse_sitemap(xml_content):
    """サイトマップ解析"""
    try:
        soup = BeautifulSoup(xml_content, 'xml')
        urls = [loc.text for loc in soup.find_all('loc')]
        return urls
    except Exception as e:
        st.error(f"サイトマップの解析に失敗しました: {e}")
        return []

def scrape_page_content(url, user=None, pw=None):
    """ベーシック認証対応スクレイピング"""
    headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/140.0.0.0 Safari/537.36"}
    auth = HTTPBasicAuth(user, pw) if user and pw else None
    
    try:
        res = requests.get(url, headers=headers, auth=auth, timeout=15)
        res.encoding = res.apparent_encoding
        
        if res.status_code == 401:
            return "認証失敗", "ID/PWが違います"
        if res.status_code != 200:
            return "取得失敗", f"HTTP {res.status_code}"
        
        soup = BeautifulSoup(res.text, 'html.parser')
        title = soup.title.string if soup.title else "タイトルなし"
        for s in soup(["script", "style", "nav", "footer", "header"]):
            s.decompose()
        body = soup.get_text(separator=' ', strip=True)[:1500]
        return title, body
    except Exception as e:
        return "取得失敗", str(e)

def generate_description(api_key, url, title, body, company):
    """AI生成（モデル自動選択）"""
    try:
        genai.configure(api_key=api_key)
        # 2026年現在の最新モデルを探す
        model = genai.GenerativeModel("gemini-3-flash")
        
        c_rule = f"・社名は必ず「{company}」とすること。" if company else ""
        prompt = f"""SEOコピーライターとして、以下のページのmeta descriptionを120〜150文字の日本語で作成してください。最後は必ず句点で完結させ、余計な注釈は一切含めないこと。{c_rule}
        URL: {url} / タイトル: {title} / 内容: {body}"""
        
        response = model.generate_content(prompt)
        return re.sub(r'[\(（]\d+文字[\)）]', '', response.text).strip()
    except Exception as e:
        return f"AIエラー: {str(e)}"

# --- メイン処理 ---

uploaded_file = st.file_uploader("sitemap.xml をアップロード", type="xml")

if uploaded_file and api_key_input:
    urls = parse_sitemap(uploaded_file)
    if urls:
        st.info(f"{len(urls)} 件のURLが見つかりました。")
        
        # 実行ボタン
        if st.button("生成を開始する"):
            results = []
            progress_bar = st.progress(0)
            status = st.empty()
            
            for i, url in enumerate(urls):
                status.write(f"⏳ 処理中 ({i+1}/{len(urls)}): {url}")
                
                title, body = scrape_page_content(url, basic_user, basic_pw)
                
                if title not in ["取得失敗", "認証失敗"]:
                    desc = generate_description(api_key_input, url, title, body, target_company)
                else:
                    desc = f"読み込めませんでした: {body}"
                
                results.append({"URL": url, "タイトル": title, "生成結果": desc})
                progress_bar.progress((i + 1) / len(urls))
                time.sleep(1)
            
            status.success("✅ 完了しました！")
            df = pd.DataFrame(results)
            
            # 結果を画面に表示
            st.write(df)
            
            # レポート（リンク付き）
            html_report = f"<html><head><meta charset='UTF-8'></head><body><h1>Report</h1>{df.to_html(render_links=True, escape=False)}</body></html>"
            st.download_button("HTML保存", html_report, "report.html", "text/html")
    else:
        st.error("サイトマップの中にURLが見つかりませんでした。ファイルを確認してください。")

elif not api_key_input:
    st.warning("APIキーを入力してください。")
