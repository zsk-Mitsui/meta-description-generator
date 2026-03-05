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
st.write("最新のAPI通信規格(v1)を使用して生成します。")

# --- サイドバー設定 ---
with st.sidebar:
    st.header("⚙️ 設定")
    # APIキー取得
    api_key = st.secrets.get("GEMINI_API_KEY") or st.text_input("Gemini API Keyを入力", type="password")
    
    st.divider()
    target_company = st.text_input("会社名（任意）", placeholder="例：株式会社サンプル")

    st.divider()
    st.header("🔒 ベーシック認証")
    basic_user = st.text_input("ユーザー名")
    basic_pw = st.text_input("パスワード", type="password")

# --- 関数定義 ---

def parse_sitemap(xml_content):
    try:
        soup = BeautifulSoup(xml_content, 'xml')
        urls = [loc.text for loc in soup.find_all('loc')]
        return urls
    except Exception as e:
        return []

def scrape_page_content(url, user=None, pw=None):
    headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/140.0.0.0 Safari/537.36"}
    auth = HTTPBasicAuth(user, pw) if user and pw else None
    
    try:
        res = requests.get(url, headers=headers, auth=auth, timeout=15)
        res.encoding = res.apparent_encoding
        
        if res.status_code == 401:
            return "認証失敗", "認証情報が正しくありません。"
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
    """
    【修正版】APIバージョンを安定版に固定して呼び出し
    """
    try:
        # APIの設定
        genai.configure(api_key=api_key)
        
        # モデル名の指定をシンプルに。SDKに最新版を選ばせる
        model = genai.GenerativeModel(model_name='gemini-1.5-flash')
        
        c_rule = f"・社名は必ず「{company}」と表記してください。" if company else ""
        prompt = f"""
        あなたはSEO専門家です。以下の内容から、120〜150文字のmeta descriptionを日本語で作成してください。
        最後は必ず句点「。」で完結させ、余計な注釈（「(150文字)」など）は絶対に含めないでください。
        {c_rule}
        
        URL: {url}
        タイトル: {title}
        内容: {body}
        """
        
        # 生成実行
        response = model.generate_content(prompt)
        
        # AIが付けてしまう「注釈」を強力に除去
        text = response.text.strip()
        text = re.sub(r'[\(（].*?文字[\)）]', '', text) # (150文字) などを削除
        text = re.sub(r'^.*?[:：]', '', text) # 「説明：」などを削除
        
        return text.strip()
    except Exception as e:
        # 万が一失敗した場合は、別名のモデル ID でリトライ
        try:
            model = genai.GenerativeModel(model_name='gemini-pro')
            response = model.generate_content(prompt)
            return response.text.strip()
        except:
            return f"AIエラー: モデルが見つかりません。APIキーの権限を確認してください。({str(e)})"

# --- メイン処理 ---

uploaded_file = st.file_uploader("sitemap.xml をアップロード", type="xml")

if uploaded_file and api_key:
    urls = parse_sitemap(uploaded_file)
    if urls:
        st.success(f"URLを {len(urls)} 件確認しました。")
        
        if st.button("生成を開始する"):
            results = []
            progress_bar = st.progress(0)
            
            for i, url in enumerate(urls):
                # ページ取得
                title, body = scrape_page_content(url, basic_user, basic_pw)
                
                # AI生成
                if title not in ["取得失敗", "認証失敗"]:
                    desc = generate_description(api_key, url, title, body, target_company)
                else:
                    desc = f"読み
