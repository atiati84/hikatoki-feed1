import os
import time
from datetime import datetime, timezone
from flask import Flask, jsonify, request
from atproto import Client

app = Flask(__name__)

# --- 基本設定 ---
SERVICE_URL = "hikatoki-feed1.onrender.com"
FEED_DID = f"did:web:{SERVICE_URL}"

client = Client()
client.login(os.environ.get("BSKY_HANDLE"), os.environ.get("BSKY_APP_PASSWORD"))

# 除外ワード（共通）
BAD_WORDS = ["母畜", "野裸", "天体", "鸡巴", "射精", "打飞机", "黄推", "傻逼", "裸聊","暗河传","bandcamp"]

# --- キャッシュ用の変数（フィードごとに分けました） ---
cache = {
    "hikatoki": {"posts": [], "time": 0},
    "novel": {"posts": [], "time": 0}
}
CACHE_DURATION = 60

# 重み付けスコア計算
def score_post(post):
    likes = post.like_count or 0
    reposts = post.repost_count or 0
    created_at = datetime.fromisoformat(post.indexed_at.replace("Z", "+00:00"))
    hours_age = (datetime.now(timezone.utc) - created_at).total_seconds() / 3600
    gravity = 2.2
    return (likes + reposts + 1) / pow((hours_age + 2), gravity)

# 投稿取得メイン関数
def get_all_filtered_posts(keywords, is_novel=False):
    all_posts = []
    for word in keywords:
        try:
            res = client.app.bsky.feed.search_posts(params={"q": word, "limit": 100})
            for p in res.posts:
                text = (p.record.text or "").lower()
                
                # 小説フィードの場合：100文字以上かチェック
                if is_novel and len(text) < 100:
                    continue
                
                # キーワードが含まれているか
                if word.lower() in text:
                    all_posts.append(p)
                else:
                    # Altテキストチェック
                    embed = getattr(p.record, 'embed', None)
                    if embed and hasattr(embed, 'images'):
                        alt = "".join([img.alt for img in embed.images if getattr(img, 'alt', None)]).lower()
                        if word.lower() in alt:
                            all_posts.append(p)
        except: continue

    unique = {p.uri: p for p in all_posts}
    return [p for p in unique.values() if not any(bw in (p.record.text or "").lower() for bw in BAD_WORDS)]

# --- メインエンドポイント ---
@app.route("/xrpc/app.bsky.feed.getFeedSkeleton")
def get_feed_skeleton():
    feed_uri = request.args.get("feed", "")
    now = time.time()
    
    # どのフィードを求められているか判定
    if "hikatoki-novel" in feed_uri:
        target = "novel"
        keywords = ["創作BL", "#創作BL"]
    else:
        target = "hikatoki"
        keywords = ["ヒカトキ", "hktk", "유진시우", "光时"]

    # キャッシュ確認
    c = cache[target]
    if c["posts"] and (now - c["time"] < CACHE_DURATION):
        final_list = c["posts"]
    else:
        # 新しく取得
        final_list = get_all_filtered_posts(keywords, is_novel=(target == "novel"))
        cache[target] = {"posts": final_list, "time": now}

    # 表示の並び替え
    if "hikatoki-new" in feed_uri or target == "novel":
        # 新着順
        final_list.sort(key=lambda p: p.indexed_at, reverse=True)
    else:
        # ヒカトキ人気順（日本語優先）
        jp = sorted([p for p in final_list if p.record.langs and "ja" in p.record.langs], key=score_post, reverse=True)
        others = sorted([p for p in final_list if p not in jp], key=score_post, reverse=True)
        final_list = jp[:30] + others

    return jsonify({"feed": [{"post": p.uri} for p in final_list[:100]]})

@app.route("/.well-known/did.json")
def did_json():
    return jsonify({"@context": ["https://www.w3.org/ns/did/v1"],"id": FEED_DID,"service": [{"id": "#bsky_fg","type": "BskyFeedGenerator","serviceEndpoint": f"https://{SERVICE_URL}"}]})

@app.route("/")
def index():
    return "Multi-Feed Server is running!"

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 10000)))
