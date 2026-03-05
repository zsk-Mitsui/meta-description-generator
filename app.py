import streamlit as st
import pandas as pd
import requests
from requests.auth import HTTPBasicAuth
from bs4 import BeautifulSoup
import google.generativeai as genai
import time
import re

# --- 基本設定 ---
st.set_page_config(page_title="SEO Meta Description Generator", layout="wide")

st.title("🚀 プロ仕様 SEO Meta Generator")
st.write("2026年最新のAPI環境に合わせて、最適なモデルを自動選択して生成します。")

# --- サイドバー設定 ---
with st.sidebar:
    st.header("⚙️ 設定")
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
        # 不要タグ削除
        for s in soup(["script", "style", "nav", "footer"]): s.decompose()
        body = soup.get_text(separator=' ', strip=True)[:1500]
        
        # プレースホルダー（{企業名}など）が含まれる場合の警告
        if "{" in title and "}" in title:
            title = f"【要確認】{title}"
            
        return title, body
    except Exception as e: return "取得失敗", str(e)

def get_best_model_name(api_key):
    """利用可能なモデルの中から最適なものを探す"""
    try:
        genai.configure(api_key=api_key)
        # 利用可能なモデルを取得
        available_models = [m.name for m in genai.list_models() if 'generateContent' in m.supported_generation_methods]
        
        # 2026年に推奨されるモデルの優先順位
        priorities = [
            "models/gemini-1.5-flash",
            "models/gemini-1.5-flash-latest",
            "models/gemini-pro",
            "models/gemini-1.0-pro"
        ]
        
        for p in priorities:
            if p in available_models:
                return p
        return available_models[0] if available_models else None
    except Exception:
        return "models/gemini-1.5-flash" # フォールバック

def generate_description(api_key, model_name, url, title, body, company):
    try:
        genai.configure(api_key=api_key)
        model = genai.GenerativeModel(model_name)
        
        c_rule = f"・社名は「{company}」で統一すること。" if company else ""
        prompt = f"""SEOのプロとして、以下のページのmeta descriptionを120〜150文字の日本語で作成してください。
        最後は句点「。」で終わらせ、注釈は一切含めないこと。{c_rule}
        URL: {url} / タイトル: {title} / 内容: {body}"""
        
        response = model
