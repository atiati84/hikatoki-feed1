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

    # 人気順（いいね + リポスト）
    posts.sort(
        key=lambda p: (p.like_count or 0) + (p.repost_count or 0),
        reverse=True
    )

    # 形式を整える
    feed = [{"post": p.uri} for p in posts[:50]]

    return jsonify({
        "feed": feed
    })

# --- エンドポイント3: サーバーの生存確認用（任意） ---
@app.route("/")
def index():
    return "Hikatoki Feed Generator is running!"

if __name__ == "__main__":
    # Renderのポート指定に対応
    port = int(os.environ.get("PORT", 10000))
    app.run(host="0.0.0.0", port=port)
