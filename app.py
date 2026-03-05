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
st.write("各ディスクリプション右上のアイコンをクリックして、瞬時にコピー可能です。")

# --- サイドバー設定 ---
with st.sidebar:
    st.header("⚙️ 設定")
    api_key = st.secrets.get("GEMINI_API_KEY") or st.text_input("Gemini API Keyを入力", type="password")
    
    st.divider()
    target_company = st.text_input(
        "会社名・ブランド名（任意）", 
        placeholder="例：株式会社サンプル",
        help="ここに入力すると、AIが全ページでこの名称を正確に使用します。空欄の場合はページ内容から自動判別します。"
    )

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
        for s in soup(["script", "style", "nav", "footer", "header"]): s.decompose()
        body = soup.get_text(separator=' ', strip=True)[:1500]
        
        if "{" in title and "}" in title: title = f"【要確認】{title}"
        return title, body
    except Exception as e: return "取得失敗", str(e)

def get_best_model_name(api_key):
    try:
        genai.configure(api_key=api_key)
        available_models = [m.name for m in genai.list_models() if 'generateContent' in m.supported_generation_methods]
        priorities = ["models/gemini-1.5-flash", "models/gemini-1.5-flash-latest", "models/gemini-pro"]
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
                
                results.append({
                    "URL": url, 
                    "タイトル": title, 
                    "生成ディスクリプション": desc,
                    "文字数": char_count
                })
                progress_bar.progress((i + 1) / len(urls))
                time.sleep(1)
            
            st.success("✅ 全ページの処理が完了しました！")
            
            # --- 1. 概要表 (UI表示) ---
            df = pd.DataFrame(results)
            st.write("### 📊 生成結果サマリー")
            st.dataframe(
                df,
                column_config={
                    "URL": st.column_config.LinkColumn("URL"),
                    "文字数": st.column_config.NumberColumn("文字数", format="%d 字")
                },
                hide_index=True,
                use_container_width=True
            )
            
            # --- 2. コピペ用セクション (新機能！) ---
            st.divider()
            st.write("### 📋 コピペ用リスト (右上のアイコンでコピー)")
            
            for i, res in enumerate(results):
                # 1ページ分を枠で囲む
                with st.container(border=True):
                    c1, c2 = st.columns([4, 1])
                    with c1:
                        st.markdown(f"**[{i+1}] {res['タイトル']}**")
                        st.caption(res['URL'])
                    with c2:
                        st.write(f"📏 {res['文字数']} 字")
                    
                    # ここがコピー機能のキモ
                    st.code(res['生成ディスクリプション'], language=None)
            
            # --- 3. ダウンロード用HTML作成 ---
            html_rows = "".join([f"<tr><td><a href='{r['URL']}'>{r['URL']}</a></td><td>{r['タイトル']}</td><td>{r['生成ディスクリプション']}</td><td>{r['文字数']}</td></tr>" for r in results])
            full_html = f"<html><head><meta charset='UTF-8'><style>body{{font-family:sans-serif;padding:20px;}} table{{width:100%;border-collapse:collapse;font-size:14px;}} th{{background:#007bff;color:white;padding:10px;text-align:left;}} td{{border:1px solid #ddd;padding:10px;}}</style></head><body><h1>SEO Report</h1><table><tr><th>URL</th><th>タイトル</th><th>生成結果</th><th>文字数</th></tr>{html_rows}</table></body></html>"
            
            st.download_button("レポート（HTML）を保存", full_html, "seo_meta_report.html", "text/html")
    else:
        st.error("URLが見つかりません。")
