import streamlit as st
import pandas as pd
import requests
from bs4 import BeautifulSoup
import google.generativeai as genai
import time
import re

# --- 基本設定 ---
st.set_page_config(page_title="プロ仕様 SEO Meta Generator", layout="wide")

st.title("🚀 プロ仕様 SEO Meta Description 生成アプリ")
st.write("会社名の統一、150文字制限、リンク付きレポート出力を備えた決定版です。")

# --- サイドバー設定 ---
with st.sidebar:
    st.header("⚙️ 設定")
    api_key = st.secrets.get("GEMINI_API_KEY") or st.text_input("Gemini API Key", type="password")
    st.divider()
    
    # プレースホルダーを汎用的にし、ヘルプを追加
    target_company = st.text_input(
        "会社名・ブランド名（任意）", 
        placeholder="例：株式会社サンプル、合同会社ABC",
        help="ここに入力すると、AIが全ページでこの名称を正確に使用します。空欄の場合はページ内容から自動判別します。"
    )

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
    try:
        genai.configure(api_key=api_key)
        models = [m.name for m in genai.list_models() if 'generateContent' in m.supported_generation_methods]
        priority = ["models/gemini-3-flash", "models/gemini-1.5-flash-latest"]
        for p in priority:
            if p in models: return p
        return models[0] if models else "models/gemini-1.5-flash"
    except:
        return "models/gemini-3-flash"

def generate_description(api_key, model_name, url, title, body_text, company_name):
    try:
        genai.configure(api_key=api_key)
        model = genai.GenerativeModel(model_name)
        
        company_rule = f"・会社名やブランド名は、必ず「{company_name}」と表記すること。" if company_name else ""
        
        prompt = f"""
        あなたは熟練のSEOコピーライターです。
        以下のページ内容から、検索ユーザーの目を引くmeta descriptionを日本語で作成してください。

        【厳守ルール】
        ・文章は必ず最後（句点「。」）まで書ききり、自然に完結させること。
        ・文字数は「120文字〜145文字」程度を目標に作成し、最大でも155文字以内には収めること。
        ・絶対に文章の途中で終わらせないこと。
        ・「（150文字）」などの注釈や、文字数カウント、解説は一切含めず、本文のみを出力すること。
        {company_rule}

        URL: {url}
        タイトル: {title}
        内容: {body_text}
        """
        response = model.generate_content(prompt)
        text = response.text.strip()
        
        # クリーニング
        text = re.sub(r'[\(（]\d+文字[\)）]', '', text)
        text = re.sub(r'^.*?[:：]', '', text)
        return text.strip()
    except Exception as e:
        return f"エラー: {str(e)}"

# --- メイン処理 ---

uploaded_file = st.file_uploader("sitemap.xml をアップロード", type="xml")

if uploaded_file and api_key:
    urls = parse_sitemap(uploaded_file)
    st.success(f"{len(urls)} 件のURLを読み込みました。")
    target_model = get_latest_model(api_key)
    
    if st.button("全ページの生成を開始"):
        results = []
        progress_bar = st.progress(0)
        
        for i, url in enumerate(urls):
            title, body = scrape_page_content(url)
            if title != "取得失敗":
                description = generate_description(api_key, target_model, url, title, body, target_company)
            else:
                description = f"スキップ ({body})"
            
            # URLをリンクタグ形式に変換
            linked_url = f'<a href="{url}" target="_blank">{url}</a>'
            
            results.append({
                "URL": linked_url,
                "タイトル": title,
                "生成ディスクリプション": description,
                "文字数": len(description)
            })
            progress_bar.progress((i + 1) / len(urls))
            time.sleep(1)
            
        df = pd.DataFrame(results)
        
        # 画面表示用（リンクをHTMLとして解釈させる）
        st.write("### 生成結果")
        st.write(df.to_html(escape=False, index=False), unsafe_allow_html=True)
        
        # HTMLレポート出力
        html_table = df.to_html(classes='table', index=False, escape=False)
        html_report = f"""
        <html>
        <head>
            <meta charset='UTF-8'>
            <style>
                body {{ font-family: sans-serif; padding: 30px; color: #333; }}
                table {{ border-collapse: collapse; width: 100%; }}
                th {{ background: #007bff; color: white; padding: 12px; text-align: left; }}
                td {{ padding: 12px; border-bottom: 1px solid #eee; font-size: 14px; vertical-align: top; }}
                tr:hover {{ background: #f8f9fa; }}
                a {{ color: #007bff; text-decoration: none; }}
                a:hover {{ text-decoration: underline; }}
            </style>
        </head>
        <body>
            <h1>SEO Meta Description Report</h1>
            <p>※URLをクリックするとページを確認できます。</p>
            {html_table}
        </body>
        </html>
        """
        st.download_button("レポート（HTML）を保存", html_report, "seo_meta_report.html", "text/html")
