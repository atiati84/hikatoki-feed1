import os
from flask import Flask, jsonify
from atproto import Client

app = Flask(__name__)

# --- 設定項目 ---
# RenderのURL（末尾のスラッシュなし）
SERVICE_URL = "hikatoki-feed1.onrender.com"
# このフィードサーバーを識別するためのID
FEED_DID = f"did:web:{SERVICE_URL}"

# Bluesky login
handle = os.environ.get("BSKY_HANDLE")
password = os.environ.get("BSKY_APP_PASSWORD")

client = Client()
client.login(handle, password)

KEYWORDS = [
    "ヒカトキ",
    "光时",
    "hktk",
    "guangshi"
]

# --- 除外したいワードのリストを追加 ---
BAD_WORDS = [
    "母畜", "野裸", "天体", "鸡巴", "射精", "打飞机", "黄推", "傻逼"
]

# --- エンドポイント1: DIDの本人確認用 (追加) ---
@app.route("/.well-known/did.json")
def did_json():
    return jsonify({
        "@context": ["https://www.w3.org/ns/did/v1"],
        "id": FEED_DID,
        "service": [
            {
                "id": "#bsky_fg",
                "type": "BskyFeedGenerator",
                "serviceEndpoint": f"https://{SERVICE_URL}"
            }
        ]
    })

# --- エンドポイント2: フィードの本体 ---
@app.route("/xrpc/app.bsky.feed.getFeedSkeleton")
def get_feed_skeleton():
    posts = []
    
    # 検索の実行
    for word in KEYWORDS:
        try:
            res = client.app.bsky.feed.search_posts(
                params={
                    "q": word,
                    "limit": 25
                }
            )
            posts.extend(res.posts)
        except Exception as e:
            print(f"Error searching for {word}: {e}")

    # 重複除去
    unique = {}
    for p in posts:
        unique[p.uri] = p
    posts = list(unique.values())
    # --- フィルタリング処理を追加 ---
    filtered_posts = []
    for p in unique.values():
        # 投稿本文(text)を取得
        text = p.record.text if hasattr(p, 'record') else ""
        
        # BAD_WORDSが含まれているかチェック
        is_bad = any(bad_word in text for bad_word in BAD_WORDS)
        
        # 含まれていなければリストに追加
        if not is_bad:
            filtered_posts.append(p)

    # フィルタリング後のリストをソート
    # 人気順（いいね + リポスト）
    filtered_posts.sort(
        key=lambda p: (p.like_count or 0) + (p.repost_count or 0),
        reverse=True
    )
    # 形式を整える
    feed = [{"post": p.uri} for p in filtered_posts[:50]]
    return jsonify({"feed": feed})


# --- エンドポイント3: サーバーの生存確認用（任意） ---
@app.route("/")
def index():
    return "Hikatoki Feed Generator is running!"

if __name__ == "__main__":
    # Renderのポート指定に対応
    port = int(os.environ.get("PORT", 10000))
    app.run(host="0.0.0.0", port=port)
