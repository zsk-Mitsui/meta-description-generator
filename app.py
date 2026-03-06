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
def local_css():
    st.markdown("""
        <style>
        .report-table { width: 100%; border-collapse: collapse; font-size: 14px; table-layout: fixed; }
        .report-table th { background-color: #007bff; color: white; padding: 12px; text-align: left; }
        .report-table td { border: 1px solid #ddd; padding: 12px; vertical-align: top; word-wrap: break-word; white-space: normal; }
        .report-table tr:nth-child(even) { background-color: #f9f9f9; }
        </style>
    """, unsafe_allow_html=True)

# --- 1. ログイン認証 ---
def login():
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

# ログインチェックを実行
if login():
    # ログイン成功後のメインコンテンツ
    local_css()
    st.title("🚀 プロ仕様 SEO Meta Description 生成アプリ")
    st.caption("Advanced Refactored Version 2026 / ログイン済み")

    # --- サイドバー設定 ---
    with st.sidebar:
        st.header("⚙️ 設定")
        api_key = st.secrets.get("GEMINI_API_KEY") or st.text_input("Gemini API Keyを入力", type="password")
        st.divider()
        target_company = st.text_input("社名の指定 (空欄ならAIが自動判定)", placeholder="例：株式会社サンプル")
        st.divider()
        st.header("🔒 ベーシック認証")
        b_user = st.text_input("User")
        b_pw = st.text_input("PW", type="password")
        
        st.markdown("<br><br>", unsafe_allow_html=True)
        st.divider()
        if st.button("🚪 ログアウト"):
            del st.session_state["password_correct"]
            st.rerun()

    # --- 2. 処理関数群 ---
    def scrape_page(url, session, auth):
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
        except Exception as e: return "取得失敗", str(e)

    def generate_meta(model, url, title, body, company):
        try:
            prompt = f"SEO専門家として、以下の内容から120〜145文字の日本語meta descriptionを作成してください。社名は「{company}」で統一し、最後は句点で完結、注釈は不要です。\nURL: {url} / タイトル: {title} / 内容: {body}"
            response = model.generate_content(prompt)
            return re.sub(r'[\(（
