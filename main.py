import os
from datetime import datetime, timezone
from flask import Flask, jsonify, request
from atproto import Client

app = Flask(__name__)

# --- 設定 ---
SERVICE_URL = "hikatoki-feed1.onrender.com"
FEED_DID = f"did:web:{SERVICE_URL}"

client = Client()
client.login(os.environ.get("BSKY_HANDLE"), os.environ.get("BSKY_APP_PASSWORD"))

KEYWORDS = ["ヒカトキ", "光时", "hktk"]
BAD_WORDS = ["母畜", "野裸", "天体", "鸡巴", "射精", "打飞机", "黄推", "傻逼"]

# --- 共通の取得・フィルタリング関数 ---
def get_filtered_posts():
    all_posts = []
    for word in KEYWORDS:
        try:
            res = client.app.bsky.feed.search_posts(params={"q": word, "limit": 40})
            all_posts.extend(res.posts)
        except: continue

    unique = {p.uri: p for p in all_posts}
    # フィルタリング（除外ワード）
    return [p for p in unique.values() if not any(bw in (p.record.text or "") for bw in BAD_WORDS)]

# --- 人気順の重み付け計算 (SkyFeedのGravity風) ---
def score_post(post):
    likes = post.like_count or 0
    reposts = post.repost_count or 0
    # 投稿からの経過時間（時間単位）を計算
    created_at = datetime.fromisoformat(post.indexed_at.replace("Z", "+00:00"))
    hours_age = (datetime.now(timezone.utc) - created_at).total_seconds() / 3600
    
    # スコア = (いいね + リポスト) / (経過時間 + 2)^Gravity
    # Gravityを 2.0 に設定（数字が大きいほど新しい投稿が有利）
    gravity = 2.0
    score = (likes + reposts) / pow((hours_age + 2), gravity)
    return score

# --- メインロジック ---
@app.route("/xrpc/app.bsky.feed.getFeedSkeleton")
def get_feed_skeleton():
    # どのフィードが呼ばれたか確認
    feed_uri = request.args.get("feed", "")
    posts = get_filtered_posts()

    # 1. 新着順フィードの場合 (rkeyを hikatoki-new にすると想定)
    if "hikatoki-new" in feed_uri:
        posts.sort(key=lambda p: p.indexed_at, reverse=True)
    
    # 2. 人気順フィードの場合 (デフォルト)
    else:
        # 日本語投稿とそれ以外に分ける
        jp_posts = [p for p in posts if (p.record.langs and "ja" in p.record.langs)]
        other_posts = [p for p in posts if p not in jp_posts]
        
        # それぞれスコア順に並べる
        jp_posts.sort(key=score_post, reverse=True)
        other_posts.sort(key=score_post, reverse=True)
        
        # 日本語30件 + 残り全部 の順で合体
        posts = jp_posts[:30] + other_posts

    return jsonify({"feed": [{"post": p.uri} for p in posts[:50]]})

@app.route("/.well-known/did.json")
def did_json():
    return jsonify({
        "@context": ["https://www.w3.org/ns/did/v1"],
        "id": FEED_DID,
        "service": [{"id": "#bsky_fg", "type": "BskyFeedGenerator", "serviceEndpoint": f"https://{SERVICE_URL}"}]
    })

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 10000)))
