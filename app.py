import streamlit as st
import pandas as pd
import requests
from bs4 import BeautifulSoup
import google.generativeai as genai
import time

# --- 基本設定 ---
st.set_page_config(page_title="SEO Meta Description Generator", layout="wide")

st.title("🚀 SEO Meta Description 生成アプリ (全件一括版)")
st.write("sitemap.xmlを読み込み、全ページのディスクリプションを自動作成します。")

# SecretsまたはサイドバーからAPIキーを取得
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
    """URLからタイトルと本文を取得（拒否対策済み）"""
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36"
    }
    try:
        res = requests.get(url, headers=headers, timeout=15)
        res.encoding = res.apparent_encoding
        if res.status_code != 200:
            return f"Error {res.status_code}", "ページにアクセスできませんでした。"
            
        soup = BeautifulSoup(res.text, 'html.parser')
        title = soup.title.string if soup.title else "タイトルなし"
        
        for script_or_style in soup(["script", "style"]):
            script_or_style.decompose()
        body_text = soup.get_text(separator=' ', strip=True)[:1000]
        
        return title, body_text
    except Exception as e:
        return "取得失敗", str(e)

def generate_description(api_key, url, title, body_text):
    """Gemini APIを使用してディスクリプション生成"""
    try:
        genai.configure(api_key=api_key)
        # エラー回避のためモデル名を明示的に指定
        model = genai.GenerativeModel(model_name="gemini-1.5-flash")
        
        prompt = f"""
        あなたはSEOに精通したマーケターです。
        以下のWebページの内容を読み、検索結果でクリックされやすいmeta descriptionを作成してください。

        【条件】
        ・120文字以上、150文字以内の日本語。
        ・自然な文章で、ターゲットが興味を持つ内容にする。
        ・ページの内容と一致させる。

        URL: {url}
        タイトル: {title}
        本文抜粋: {body_text}

        meta descriptionのみを出力してください。
        """
        response = model.generate_content(prompt)
        return response.text.strip()
    except Exception as e:
        return f"AI生成エラー: {str(e)}"

# --- メイン処理 ---

uploaded_file = st.file_uploader("sitemap.xml をアップロードしてください", type="xml")

if uploaded_file and api_key:
    urls = parse_sitemap(uploaded_file)
    st.success(f"合計 {len(urls)} 件のURLが見つかりました。全件処理します。")
    
    if st.button("全ページの生成を開始する"):
        results = []
        progress_bar = st.progress(0)
        status_text = st.empty()
        
        for i, url in enumerate(urls):
            status_text.text(f"処理中 ({i+1}/{len(urls)}): {url}")
            
            # 1. ページ読み込み
            title, body = scrape_page_content(url)
            
            # 2. AI生成（ページ取得に成功した場合のみ）
            if "Error" not in title and "取得失敗" not in title:
                description = generate_description(api_key, url, title, body)
            else:
                description = f"スキップ: {body}"
            
            results.append({
                "URL": url,
                "ページタイトル": title,
                "生成ディスクリプション": description,
                "文字数": len(description)
            })
            
            # 進捗更新
            progress_bar.progress((i + 1) / len(urls))
            time.sleep(1.5) # 安全のための待機
            
        status_text.text("✨ 全ページの処理が完了しました！")
        
        # 結果表示
        df = pd.DataFrame(results)
        st.dataframe(df)
        
        # HTMLレポートの作成
        html_table = df.to_html(classes='table table-striped', index=False, escape=False)
        html_report = f"""
        <html>
        <head>
            <meta charset="UTF-8">
            <title>Meta Description Report</title>
            <style>
                body {{ font-family: 'Helvetica Neue', Arial, sans-serif; margin: 40px; color: #333; }}
                table {{ border-collapse: collapse; width: 100%; border: 1px solid #eee; }}
                th {{ background-color: #007bff; color: white; padding: 15px; text-align: left; }}
                td {{ padding: 12px; border-bottom: 1px solid #eee; font-size: 14px; }}
                tr:hover {{ background-color: #f8f9fa; }}
            </style>
        </head>
        <body>
            <h1>SEO Meta Description Report</h1>
            <p>処理URL数: {len(urls)} 件</p>
            {html_table}
        </body>
        </html>
        """
        
        st.download_button(
            label="結果をHTMLでダウンロード",
            data=html_report,
            file_name="meta_report.html",
            mime="text/html"
        )

elif not api_key:
    st.warning("APIキーが設定されていません。")
