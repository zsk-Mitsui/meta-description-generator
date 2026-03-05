import streamlit as st
import pandas as pd
import requests
from bs4 import BeautifulSoup
import google.generativeai as genai
import time

# --- 設定 ---
st.set_page_config(page_title="AI Meta Description Generator", layout="wide")

st.title("🚀 SEO Meta Description 生成アプリ")
st.write("sitemap.xmlの全URLに対して、AIがメタディスクリプションを自動作成します。")

# SecretsからAPIキーを取得
if "GEMINI_API_KEY" in st.secrets:
    api_key = st.secrets["GEMINI_API_KEY"]
else:
    with st.sidebar:
        st.header("Settings")
        api_key = st.text_input("Gemini API Keyを入力してください", type="password")

# --- 関数定義 ---

def parse_sitemap(xml_content):
    """sitemap.xmlからURLリストを抽出"""
    soup = BeautifulSoup(xml_content, 'xml')
    urls = [loc.text for loc in soup.find_all('loc')]
    return urls

def scrape_page_content(url):
    """URLからタイトルと本文の一部を取得"""
    try:
        res = requests.get(url, timeout=10)
        res.encoding = res.apparent_encoding
        soup = BeautifulSoup(res.text, 'html.parser')
        title = soup.title.string if soup.title else "タイトルなし"
        for script_or_style in soup(["script", "style"]):
            script_or_style.decompose()
        body_text = soup.get_text(separator=' ', strip=True)[:1000]
        return title, body_text
    except Exception as e:
        return "取得エラー", str(e)

def generate_description(api_key, url, title, body_text):
    """Gemini APIを使用してディスクリプション生成"""
    try:
        genai.configure(api_key=api_key)
        # モデル名を最新の安定版 'gemini-1.5-flash' に指定
        model = genai.GenerativeModel('gemini-1.5-flash')
        
        prompt = f"""
        あなたはプロのSEOライターです。以下のWebページの内容に基づき、SEOに最適化されたmeta descriptionを作成してください。
        
        【ルール】
        1. 日本語で120文字から150文字の間。
        2. ユーザーが思わずクリックしたくなる魅力的な文章にする。
        3. ページ内容を正確に要約し、キーワードを自然に含める。
        
        【ページ情報】
        URL: {url}
        タイトル: {title}
        本文抜粋: {body_text}
        
        descriptionの文章のみを出力してください。
        """
        response = model.generate_content(prompt)
        return response.text.strip()
    except Exception as e:
        return f"生成エラー: {str(e)}"

# --- メイン処理 ---

uploaded_file = st.file_uploader("sitemap.xml をアップロードしてください", type="xml")

if uploaded_file and api_key:
    urls = parse_sitemap(uploaded_file)
    st.success(f"{len(urls)} 件のURLをすべて処理対象として読み込みました。")
    
    # 実行ボタン
    if st.button("全ページの生成を開始する"):
        results = []
        progress_bar = st.progress(0)
        status_text = st.empty()
        
        for i, url in enumerate(urls):
            status_text.text(f"処理中 ({i+1}/{len(urls)}): {url}")
            
            title, body = scrape_page_content(url)
            description = generate_description(api_key, url, title, body)
            
            results.append({
                "URL": url,
                "Current Title": title,
                "Generated Meta Description": description,
                "Length": len(description)
            })
            
            progress_bar.progress((i + 1) / len(urls))
            time.sleep(1) # API制限とサーバー負荷防止
            
        status_text.text("✅ すべての処理が完了しました！")
        
        # 結果表示
        df = pd.DataFrame(results)
        st.subheader("生成結果")
        st.dataframe(df)
        
        # HTMLレポートの作成
        html_table = df.to_html(classes='table table-striped', index=False, escape=False)
        html_report = f"""
        <html>
        <head>
            <meta charset="UTF-8">
            <title>Meta Description Report</title>
            <style>
                body {{ font-family: sans-serif; margin: 40px; line-height: 1.6; color: #333; }}
                table {{ border-collapse: collapse; width: 100%; margin-top: 20px; }}
                th, td {{ border: 1px solid #ddd; padding: 12px; text-align: left; }}
                th {{ background-color: #007bff; color: white; }}
                tr:nth-child(even) {{ background-color: #f9f9f9; }}
                tr:hover {{ background-color: #f1f1f1; }}
            </style>
        </head>
        <body>
            <h1>SEO Meta Description Report</h1>
            <p>生成日時: {time.strftime('%Y-%m-%d %H:%M:%S')}</p>
            {html_table}
        </body>
        </html>
        """
        
        st.download_button(
            label="HTMLレポートをダウンロード",
            data=html_report,
            file_name="meta_description_report.html",
            mime="text/html"
        )
elif not api_key:
    st.warning("APIキーが設定されていません。Secretsを確認するかサイドバーで入力してください。")
