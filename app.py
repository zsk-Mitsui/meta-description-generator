import streamlit as st
import pandas as pd
import requests
from bs4 import BeautifulSoup
import google.generativeai as genai
import time
import base64

# --- 設定 ---
st.set_page_config(page_title="AI Meta Description Generator", layout="wide")

st.title("🚀 SEO Meta Description 生成アプリ")
st.write("sitemap.xmlを読み込んで、AIが各ページのメタディスクリプションを自動作成します。")

# 1. Secretsに保存されているか確認
if "GEMINI_API_KEY" in st.secrets:
    api_key = st.secrets["GEMINI_API_KEY"]
else:
    # 2. Secretsになければ、サイドバーで手動入力を促す
    with st.sidebar:
        st.header("Settings")
        api_key = st.text_input("Gemini API Keyを入力してください", type="password")
        if not api_key:
            st.info("StreamlitのSecretsにGEMINI_API_KEYを設定すると、この入力をスキップできます。")

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
        # 不要なタグ（script, style）を削除してテキスト抽出
        for script_or_style in soup(["script", "style"]):
            script_or_style.decompose()
        body_text = soup.get_text(separator=' ', strip=True)[:1000] # 冒頭1000文字
        
        return title, body_text
    except Exception as e:
        return "取得エラー", str(e)

def generate_description(api_key, url, title, body_text):
    """Gemini APIを使用してディスクリプション生成"""
    genai.configure(api_key=api_key)
    model = genai.GenerativeModel('gemini-1.5-flash')
    
    prompt = f"""
    あなたはプロのSEOライターです。以下のWebページの内容に基づき、SEOに最適化されたmeta descriptionを作成してください。
    
    【ルール】
    1. 文字数は120文字から150文字の間。
    2. ユーザーが思わずクリックしたくなる魅力的な文章にする。
    3. キーワードを自然に含める。
    
    【ページ情報】
    URL: {url}
    タイトル: {title}
    本文抜粋: {body_text}
    
    descriptionのみを出力してください。
    """
    
    try:
        response = model.generate_content(prompt)
        return response.text.strip()
    except Exception as e:
        return f"生成エラー: {str(e)}"

# --- メイン処理 ---

uploaded_file = st.file_uploader("sitemap.xml をアップロードしてください", type="xml")

if uploaded_file and api_key:
    urls = parse_sitemap(uploaded_file)
    st.success(f"{len(urls)} 件のURLが見つかりました。")
    
    # 処理するURLの数を選択（テスト用に制限できるように）
    num_to_process = st.slider("処理するページ数を選んでください", 1, len(urls), min(5, len(urls)))

    if st.button("生成を開始する"):
        results = []
        progress_bar = st.progress(0)
        
        for i, url in enumerate(urls[:num_to_process]):
            st.write(f"処理中 ({i+1}/{num_to_process}): {url}")
            
            # スクレイピング
            title, body = scrape_page_content(url)
            
            # AI生成
            description = generate_description(api_key, url, title, body)
            
            results.append({
                "URL": url,
                "Current Title": title,
                "Generated Meta Description": description,
                "Length": len(description)
            })
            
            # 進捗更新
            progress_bar.progress((i + 1) / num_to_process)
            # サーバー負荷軽減のための待機
            time.sleep(1)
            
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
                body {{ font-family: sans-serif; margin: 40px; line-height: 1.6; }}
                table {{ border-collapse: collapse; width: 100%; }}
                th, td {{ border: 1px solid #ddd; padding: 12px; text-align: left; }}
                th {{ background-color: #f4f4f4; }}
                tr:nth-child(even) {{ background-color: #fafafa; }}
            </style>
        </head>
        <body>
            <h1>SEO Meta Description Report</h1>
            {html_table}
        </body>
        </html>
        """
        
        # ダウンロードボタン
        st.download_button(
            label="HTMLレポートをダウンロード",
            data=html_report,
            file_name="meta_description_report.html",
            mime="text/html"
        )
elif not api_key:

    st.warning("左側のサイドバーにAPIキーを入力してください。")
