def scrape_page(url, session, auth):
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/128.0.0.0 Safari/537.36",
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        "Accept-Language": "ja,en-US;q=0.9,en;q=0.8"
    }
    
    # 試行1: 通常の直接アクセス (タイムアウト短め5秒)
    try:
        res = session.get(url, headers=headers, auth=auth, timeout=(5, 10))
        if res.status_code == 200:
            res.encoding = res.apparent_encoding
            soup = BeautifulSoup(res.text, 'html.parser')
            title = (soup.title.string or "タイトルなし").strip()
            for s in soup(["script", "style", "nav", "footer", "header"]): s.decompose()
            body = soup.get_text(separator=' ', strip=True)[:1200]
            return title, body
    except Exception:
        pass  # 直接アクセスが弾かれた場合はフォールバックへ

    # 試行2: 公開プロキシAPI (AllOrigins) を経由して迂回取得
    try:
        proxy_url = f"https://api.allorigins.win/raw?url={requests.utils.quote(url)}"
        res = requests.get(proxy_url, timeout=15)
        if res.status_code == 200:
            res.encoding = res.apparent_encoding
            soup = BeautifulSoup(res.text, 'html.parser')
            title = (soup.title.string or "タイトルなし").strip()
            for s in soup(["script", "style", "nav", "footer", "header"]): s.decompose()
            body = soup.get_text(separator=' ', strip=True)[:1200]
            return title, body
    except Exception:
        pass

    # 試行3: Jina AI Reader API を経由してテキスト抽出 (クローリング特化API)
    try:
        jina_url = f"https://r.jina.ai/{url}"
        res = requests.get(jina_url, timeout=15)
        if res.status_code == 200:
            content = res.text
            # タイトルと本文を簡易パース
            lines = [l.strip() for l in content.splitlines() if l.strip()]
            title = lines[0].replace("Title:", "").strip() if lines else "タイトルなし"
            body = " ".join(lines[1:])[:1200]
            return title, body
    except Exception as e:
        return "取得失敗", f"全ルート接続失敗: {str(e)}"

    return "取得失敗", "サーバーにより海外接続が遮断されています (エックスサーバーの国外IP制限を解除してください)"
