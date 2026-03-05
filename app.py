import streamlit as st
import pandas as pd
import requests
from bs4 import BeautifulSoup
import google.generativeai as genai
import time

# --- 基本設定 ---
st.set_page_config(page_title="SEO Meta Description Generator", layout="wide")

st.title("🚀 SEO Meta Description 生成アプリ (2026年版)")
st.write("sitemap.xmlの全ページを最新のGemini 3モデルで解析し、SEOディスクリプションを作成します。")

# SecretsまたはサイドバーからAPIキーを取得
api_key = st.secrets.get("GEMINI_API_KEY") or st.sidebar.text_input("Gemini API Key", type="password")

# --- 関数定義 ---

def parse_sitemap(xml_content):
    soup = BeautifulSoup(xml_content, 'xml')
    return [loc.text for loc in soup.find_all('loc')]

def scrape_page_content(url):
    headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/140.0.0.0 Safari/537.36"}
    try:
        res = requests.get(url, headers=headers, timeout=15)
        res.encoding = res.apparent_encoding
        if res.status_code != 200:
            return "取得失敗", f"HTTP {res.status_code}"
        
        soup = BeautifulSoup(res.text, 'html.parser')
        title = soup.title.string if soup.title else "タイトルなし"
        
        for s in soup(["script", "style", "nav", "footer", "header"]):
            s.decompose()
        body_text = soup.get_text(separator=' ', strip=True)[:1500]
        
        return title, body_text
    except Exception as e:
        return "取得失敗", str(e)

def get_latest_model(api_key):
    """2026年現在の最新モデル名を自動取得する"""
    try:
        genai.configure(api_key=api_key)
        models = [m.name for m in genai.list_models() if 'generateContent' in m.supported_generation_methods]
        
        # 2026年の優先順位
        priority = ["models/gemini-3-flash", "models/gemini-1.5-flash-latest", "models/gemini-1.5-pro-latest"]
        for p in priority:
            if p in models:
                return p
        # 見つからなければ最新と思われるものを返す
        return models[0] if models else "models/gemini-1.5-flash"
    except Exception as e:
        st.error(f"モデル確認エラー: {e}")
        return "models/gemini-3-flash"

def generate_description(api_key, model_name, url, title, body_text):
    try:
        genai.configure(api_key=api_key)
        model = genai.GenerativeModel(model_name)
        
        prompt = f"""
        あなたはSEO専門家です。以下の内容から120〜150文字のmeta descriptionを日本語で作成してください。
        URL: {url}
        タイトル: {title}
        内容: {body_text}
        
        ※クリック率を高める魅力的な提案を、文章のみで出力してください。
        """
        response = model.generate_content(prompt)
        return response.text.strip()
    except Exception as e:
        return f"エラー ({model_name}): {str(e)}"

# --- メイン処理 ---

uploaded_file = st.file_uploader("sitemap.xml をアップロード", type="xml")

if uploaded_file and api_key:
    urls = parse_sitemap(uploaded_file)
    st.success(f"{len(urls)} 件のURLを読み込みました。")
    
    # 最新モデルを自動選択
    target_model = get_latest_model(api_key)
    st.info(f"使用AIモデル: {target_model}")
    
    if st.button("全ページの生成を開始"):
        results = []
        progress_bar = st.progress(0)
        
        for i, url in enumerate(urls):
            title, body = scrape_page_content(url)
            
            if title != "取得失敗":
                description = generate_description(api_key, target_model, url, title, body)
            else:
                description = f"スキップ ({body})"
            
            results.append({
                "URL": url,
                "タイトル": title,
                "生成ディスクリプション": description,
                "文字数": len(description)
            })
            progress_bar.progress((i + 1) / len(urls))
            time.sleep(1)
            
        df = pd.DataFrame(results)
        st.dataframe(df)
        
        # HTMLレポート出力
        html_table = df.to_html(classes='table', index=False, escape=False)
        html_report = f"<html><head><meta charset='UTF-8'></head><body><h1>SEO Report</h1>{html_table}</body></html>"
        st.download_button("レポートを保存", html_report, "meta_report.html", "text/html")
