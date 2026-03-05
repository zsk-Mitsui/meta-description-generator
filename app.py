import streamlit as st
import pandas as pd
import requests
from bs4 import BeautifulSoup
import google.generativeai as genai
import time

# --- 基本設定 ---
st.set_page_config(page_title="SEO Meta Description Generator", layout="wide")

st.title("🚀 SEO Meta Description 生成アプリ")
st.write("sitemap.xmlから全ページのディスクリプションを自動生成します。")

# SecretsまたはサイドバーからAPIキーを取得
api_key = st.secrets.get("GEMINI_API_KEY") or st.sidebar.text_input("Gemini API Key", type="password")

# --- 関数定義 ---

def parse_sitemap(xml_content):
    """sitemap.xmlからURLリストを抽出"""
    soup = BeautifulSoup(xml_content, 'xml')
    urls = [loc.text for loc in soup.find_all('loc')]
    return urls

def scrape_page_content(url):
    """URLからタイトルと本文を取得"""
    headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"}
    try:
        res = requests.get(url, headers=headers, timeout=15)
        res.encoding = res.apparent_encoding
        if res.status_code != 200:
            return "取得失敗", f"HTTP {res.status_code}"
            
        soup = BeautifulSoup(res.text, 'html.parser')
        title = soup.title.string if soup.title else "タイトルなし"
        
        # 不要なタグを除去
        for s in soup(["script", "style", "nav", "footer"]):
            s.decompose()
        body_text = soup.get_text(separator=' ', strip=True)[:1000]
        
        return title, body_text
    except Exception as e:
        return "取得失敗", str(e)

def get_available_model(api_key):
    """利用可能な最適なモデル名を自動で取得する"""
    try:
        genai.configure(api_key=api_key)
        # 利用可能なモデルリストを取得
        models = [m.name for m in genai.list_models() if 'generateContent' in m.supported_generation_methods]
        
        # 優先順位をつけて選定
        priority = ["models/gemini-2.0-flash", "models/gemini-1.5-flash", "models/gemini-pro"]
        for p in priority:
            if p in models:
                return p
        return models[0] if models else "models/gemini-1.5-flash"
    except Exception as e:
        st.error(f"モデルリストの取得に失敗しました: {e}")
        return "models/gemini-1.5-flash"

def generate_description(api_key, model_name, url, title, body_text):
    """指定されたモデルでディスクリプション生成"""
    try:
        genai.configure(api_key=api_key)
        model = genai.GenerativeModel(model_name)
        
        prompt = f"""
        あなたはプロのSEOコンサルタントです。
        以下のページ内容を要約し、120〜150文字の魅力的なmeta descriptionを日本語で作成してください。
        
        URL: {url}
        タイトル: {title}
        本文: {body_text}
        
        出力は、生成した文章のみにしてください。
        """
        response = model.generate_content(prompt)
        return response.text.strip()
    except Exception as e:
        return f"AI生成エラー ({model_name}): {str(e)}"

# --- メイン処理 ---

uploaded_file = st.file_uploader("sitemap.xml をアップロードしてください", type="xml")

if uploaded_file and api_key:
    urls = parse_sitemap(uploaded_file)
    st.success(f"{len(urls)} 件のURLが見つかりました。全件処理します。")
    
    # 最初に最適なモデルを特定
    target_model = get_available_model(api_key)
    st.info(f"使用モデル: {target_model}")
    
    if st.button("全ページの生成を開始する"):
        results = []
        progress_bar = st.progress(0)
        status_text = st.empty()
        
        for i, url in enumerate(urls):
            status_text.text(f"処理中 ({i+1}/{len(urls)}): {url}")
            
            # 1. スクレイピング
            title, body = scrape_page_content(url)
            
            # 2. AI生成（スクレイピング成功時のみ）
            if title != "取得失敗":
                description = generate_description(api_key, target_model, url, title, body)
            else:
                description = f"スキップ: {body}"
            
            results.append({
                "URL": url,
                "ページタイトル": title,
                "生成ディスクリプション": description,
                "文字数": len(description) if "エラー" not in description else 0
            })
            
            # 進捗
            progress_bar.progress((i + 1) / len(urls))
            time.sleep(1) # API制限回避
            
        status_text.text("✅ すべて完了しました！")
        
        # 結果表示
        df = pd.DataFrame(results)
        st.dataframe(df)
        
        # レポート出力
        html_table = df.to_html(classes='table', index=False, escape=False)
        html_report = f"""
        <html>
        <head><meta charset="UTF-8"><style>
            body {{ font-family: sans-serif; padding: 40px; }}
            table {{ border-collapse: collapse; width: 100%; }}
            th {{ background: #007bff; color: white; padding: 10px; text-align: left; }}
            td {{ padding: 10px; border-bottom: 1px solid #eee; }}
        </style></head>
        <body>
            <h1>SEO Meta Description Report</h1>
            {html_table}
        </body></html>
        """
        
        st.download_button("レポートをダウンロード", html_report, "meta_report.html", "text/html")

elif not api_key:
    st.warning("APIキーを設定してください。")
