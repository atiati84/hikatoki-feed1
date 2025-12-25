import os
from flask import Flask, jsonify, request
from atproto import Client

app = Flask(__name__)

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

@app.route("/xrpc/app.bsky.feed.getFeedSkeleton")
def get_feed_skeleton():
    posts = []

    for word in KEYWORDS:
        res = client.app.bsky.feed.search_posts(
            params={
                "q": word,
                "limit": 25
            }
        )
        posts.extend(res.posts)

    # 重複除去
    unique = {}
    for p in posts:
        unique[p.uri] = p
    posts = list(unique.values())

    # 人気順
    posts.sort(
        key=lambda p: (p.like_count or 0) + (p.repost_count or 0),
        reverse=True
    )

    # Blueskyが欲しい形式（URIだけ）
    feed = [{"post": p.uri} for p in posts[:50]]

    return jsonify({
        "feed": feed
    })

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=10000)


