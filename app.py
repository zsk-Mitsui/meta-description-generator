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
st.write("ベーシック認証のかかったテストサイトにも対応。全自動でSEOレポートを作成します。")

# --- サイドバー設定 ---
with st.sidebar:
    st.header("⚙️ API設定")
    api_key = st.secrets.get("GEMINI_API_KEY") or st.text_input("Gemini API Key", type="password")
    
    st.divider()
    st.header("🏢 会社情報")
    target_company = st.text_input(
        "正式な会社名・ブランド名", 
        placeholder="例：株式会社サンプル",
        help="全ページのディスクリプションでこの名称を統一して使用します。"
    )

    st.divider()
    st.header("🔒 ベーシック認証 (任意)")
    basic_user = st.text_input("ユーザー名", placeholder="username")
    basic_pw = st.text_input("パスワード", type="password", placeholder="password")
    if basic_user and basic_pw:
        st.caption("⚠️ ベーシック認証を有効にしてアクセスします。")

# --- 関数定義 ---

def parse_sitemap(xml_content):
    soup = BeautifulSoup(xml_content, 'xml')
    return [loc.text for loc in soup.find_all('loc')]

def scrape_page_content(url, user=None, pw=None):
    headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/140.0.0.0 Safari/537.36"}
    
    # 認証情報の準備
    auth = HTTPBasicAuth(user, pw) if user and pw else None
    
    try:
        res = requests.get(url, headers=headers, auth=auth, timeout=15)
        res.encoding = res.apparent_encoding
        
        if res.status_code == 401:
            return "認証失敗", "ベーシック認証のユーザー名またはパスワードが正しくありません。"
        if res.status_code != 200:
            return "取得失敗", f"HTTP {res.status_code} エラー"
        
        soup = BeautifulSoup(res.text, 'html.parser')
        title = soup.title.string if soup.title else "タイトルなし"
        
        # 本文抽出（不要なタグを除去）
        for s in soup(["script", "style", "nav", "footer", "header"]):
            s.decompose()
        body_text = soup.get_text(separator=' ', strip=True)[:1500]
        
        return title, body_text
    except Exception as e:
        return "取得失敗", str(e)

def get_latest_model(api_key):
    try:
        genai.configure(api_key=api_key)
        models = [m.name for m in genai.list_models() if 'generateContent' in m.supported_generation_methods]
        priority = ["models/gemini-3-flash", "models/gemini-1.5-flash-latest"]
        for p in priority:
            if p in models: return p
        return models[0] if models else "models/gemini-1.5-flash"
    except:
        return "models/gemini-3-flash"

def generate_description(api_key, model_name, url, title, body_text, company_name):
    try:
        genai.configure(api_key=api_key)
        model = genai.GenerativeModel(model_name)
        
        company_rule = f"・会社名やブランド名は、必ず「{company_name}」と表記すること。" if company_name else ""
        
        prompt = f"""
        あなたは熟練のSEOコピーライターです。
        以下のページ内容から、検索ユーザーの目を引くmeta descriptionを日本語で作成してください。

        【厳守ルール】
        ・文章は必ず最後（句点「。」）まで書ききり、自然に完結させること。
        ・文字数は「120文字〜145文字」程度を目標に作成し、最大でも155文字以内には収めること。
        ・絶対に文章の途中で終わらせないこと。
        ・注釈、カウント、解説は一切含めず、本文のみを出力すること。
        {company_rule}

        URL: {url}
        タイトル: {title}
        内容: {body_text}
        """
        response = model.generate_content(prompt)
        text = response.text.strip()
        
        # クリーニング
        text = re.sub(r'[\(（]\d+文字[\)）]', '', text)
        text = re.sub(r'^.*?[:：]', '', text)
        return text.strip()
    except Exception as e:
        return f"AI生成エラー: {str(e)}"

# --- メイン処理 ---

uploaded_file = st.file_uploader("sitemap.xml をアップロード", type="xml")

if uploaded_file and api_key:
    urls = parse_sitemap(uploaded_file)
    st.success(f"{len(urls)} 件のURLを読み込みました。")
    target_model = get_latest_model(api_key)
    
    if st.button("全ページの生成を開始"):
        results = []
        progress_bar = st.progress(0)
        
        for i, url in enumerate(urls):
            # 認証情報を渡してスクレイピング
            title, body = scrape_page_content(url, basic_user, basic_pw)
