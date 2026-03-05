import streamlit as st
import pandas as pd
import requests
from bs4 import BeautifulSoup
import google.generativeai as genai
import time

# --- 基本設定 ---
st.set_page_config(page_title="SEO Meta Description Generator", layout="wide")

st.title("🚀 SEO Meta Description 生成アプリ")
st.write("sitemap.xmlの全ページをAIが読み取り、SEOに最適なディスクリプションを自動作成します。")

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
    headers = {"User-Agent": "Mozilla/5.0"}
    try:
        res = requests.get(url, headers=headers, timeout=15)
        res.encoding = res.apparent_encoding
        if res.status_code != 200:
            return "取得失敗", f"Status Code: {res.status_code}"
            
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
        # APIの設定
        genai.configure(api_key=api_key)
        
        # 【修正ポイント】モデル名を「gemini-1.5-flash」に固定し、SDKにお任せする
        model = genai.GenerativeModel('gemini-1.5-flash')
        
        prompt = f"""
        あなたはSEOライターです。以下のWebページの内容を120〜150文字の日本語で要約し、
        検索結果でクリックしたくなる魅力的なmeta descriptionを作成してください。
        
        URL: {url}
        タイトル: {title}
        本文抜粋: {body_text}
        
        ※出力は、ディスクリプションの文章のみにしてください。
        """
        response = model.generate_content(prompt)
        return response.text.strip()
    except Exception as e:
        # エラーが出た場合、別のモデル名でもう一度だけ試す（保険）
        try:
            model = genai.GenerativeModel('gemini-1.5-pro')
            response = model.generate_content(prompt)
            return response.text.strip()
        except:
            return f"AI生成エラー: {str(e)}"

# --- メイン処理 ---

uploaded_file = st.file_uploader("sitemap.xml をアップロードしてください", type="xml")

if uploaded_file:
    if not api_key:
        st.error("APIキーが設定されていません。サイドバーに入力するか、Secretsを確認してください。")
    else:
        urls = parse_sitemap(uploaded_file)
        st.success(f"合計 {len(urls)} 件のURLを読み込みました。")
        
        # 実行ボタン（スライダーは削除しました）
        if st.button("全ページのメタディスクリプションを一括生成する"):
            results = []
            progress_bar = st.progress(0)
            status_text = st.empty()
            
            for i, url in enumerate(urls):
                status_text.text(f"処理中 ({i+1}/{len(urls)}): {url}")
                
                # ページ読み込み
                title, body = scrape_page_content(url)
                
                # 生成（取得エラーでない場合のみ実行）
                if title != "取得失敗":
                    description = generate_description(api_key, url, title, body)
                else:
                    description = f"スキップされました（{body}）"
                
                results.append({
                    "URL": url,
                    "タイトル": title,
                    "生成ディスクリプション": description,
                    "文字数": len(description)
                })
                
                # 進捗更新
                progress_bar.progress((i + 1) / len(urls))
                time.sleep(1) # APIの負荷制限対策
            
            status_text.text("✅ すべての処理が完了しました！")
            
            # 結果表示
            df = pd.DataFrame(results)
            st.dataframe(df)
            
            # HTMLレポート作成（見栄えをさらに改善）
            html_table = df.to_html(classes='table', index=False, escape=False)
            html_report = f"""
            <html>
            <head>
                <meta charset="UTF-8">
                <style>
                    body {{ font-family: sans-serif; padding: 40px; color: #444; }}
                    h1 {{ color: #007bff; border-bottom: 2px solid #007bff; }}
                    table {{ border-collapse: collapse; width: 100%; margin-top: 20px; }}
                    th {{ background: #007bff; color: white; padding: 12px; text-align: left; }}
                    td {{ padding: 12px; border-bottom: 1px solid #eee; }}
                    tr:hover {{ background: #f8f9fa; }}
                </style>
            </head>
            <body>
                <h1>SEO Meta Description レポート</h1>
                <p>生成日: {time.strftime('%Y-%m-%d')}</p>
                {html_
