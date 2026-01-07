import os
import time
from datetime import datetime, timezone
from flask import Flask, jsonify, request
from atproto import Client

app = Flask(__name__)
# ２ロード消した。あと””も消えているのでフィルタが弱い。最新は一応これ
# --- 基本設定 ---
SERVICE_URL = "hikatoki-feed1.onrender.com"
FEED_DID = f"did:web:{SERVICE_URL}"

# Bluesky ログイン
client = Client()
client.login(os.environ.get("BSKY_HANDLE"), os.environ.get("BSKY_APP_PASSWORD"))

# キーワードと除外ワード
KEYWORDS = ["ヒカトキ", "hktk", "유진시우", "光时"]
BAD_WORDS = ["母畜", "野裸", "天体", "鸡巴", "射精", "打飞机", "黄推", "傻逼", "裸聊","暗河传","bandcamp"]

# --- キャッシュ用の変数 ---
cache_posts = []
cache_time = 0
CACHE_DURATION = 20  # ○秒間キャッシュを保持

# --- 投稿の取得とフィルタリング ---
def get_filtered_posts():
    global cache_posts, cache_time
    now = time.time()
    if cache_posts and (now - cache_time < CACHE_DURATION):
        return cache_posts

    all_posts = []
    for word in KEYWORDS:
        try:
            # 作戦1: " を外して、検索エンジンには「広めに候補を出して」と頼む
            res = client.app.bsky.feed.search_posts(params={
                "q": word, 
                "limit": 100 # 1回で最大100件取得
            })
            
            for p in res.posts:
                text = (p.record.text or "").lower()
                alt_texts = ""
                # Altテキストの取得（安全な書き方に整理）
                embed = getattr(p.record, 'embed', None)
                if embed and hasattr(embed, 'images'):
                    alt_texts = "".join([img.alt for img in embed.images if getattr(img, 'alt', None)]).lower()
                
                # ここで「文字が繋がっているか」を厳密にチェック
                # これがあるから、検索クエリに " がなくても大丈夫！
                if word.lower() in text or word.lower() in alt_texts:
                    all_posts.append(p)
        except Exception as e:
            print(f"Error: {e}")
            continue

    # 重複除去
    unique_dict = {p.uri: p for p in all_posts}
    # フィルタリング（BAD_WORDS）
    filtered = [p for p in unique_dict.values() if not any(bw in (p.record.text or "").lower() for bw in BAD_WORDS)]
    
    # 件数が少ない場合、もし必要ならここで追加のログを出して確認もできます
    print(f"DEBUG: Found {len(filtered)} posts")

    cache_posts = filtered
    cache_time = now
    return filtered

# --- 重み付けスコア計算 (SkyFeedのGravity風) ---
def score_post(post):
    likes = post.like_count or 0
    reposts = post.repost_count or 0
    
    # 投稿からの経過時間（時間単位）を計算
    created_at = datetime.fromisoformat(post.indexed_at.replace("Z", "+00:00"))
    hours_age = (datetime.now(timezone.utc) - created_at).total_seconds() / 3600
    
    # スコア = (いいね + リポスト + 1) / (経過時間 + 2)^Gravity
    # Gravityを 2.2 に設定（お好みで 2.0 〜 4.0 で調整してください）
    gravity = 2.2
    score = (likes + reposts + 1) / pow((hours_age + 2), gravity)
    return score

# --- メインエンドポイント ---
@app.route("/xrpc/app.bsky.feed.getFeedSkeleton")
def get_feed_skeleton():
    feed_uri = request.args.get("feed", "")
    all_posts = get_filtered_posts()
    
    # 1. 新着順 (URIに hikatoki-new が含まれる場合)
    if "hikatoki-new" in feed_uri:
        # indexed_at（Blueskyが投稿を検知した時間）でソート
        all_posts.sort(key=lambda p: p.indexed_at, reverse=True)
        final_posts = all_posts
        
    # 2. 人気順（デフォルト）
    else:
        # 日本語とそれ以外に分ける
        jp_posts = [p for p in all_posts if (p.record.langs and "ja" in p.record.langs)]
        other_posts = [p for p in all_posts if p not in jp_posts]
        
        # それぞれをGravityスコアでソート
        jp_posts.sort(key=score_post, reverse=True)
        other_posts.sort(key=score_post, reverse=True)
        
        # 日本語30件を優先し、その後に残りの日本語＋外国語を結合
        final_posts = jp_posts[:30] + [p for p in jp_posts[30:] + other_posts]
        # 全体でも再度スコア順にしたい場合はここを調整しますが、
        # 「日本語30件→その他」の順にしています。

    # 上位100件を返却
    # ※Blueskyアプリ側で一度に表示できる上限に近づけます
    feed = [{"post": p.uri} for p in final_posts[:100]]
    return jsonify({"feed": feed})

# --- DID証明 ---
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

# --- トップページ（Renderの動作確認用） ---
@app.route("/")
def index():
    return f"Hikatoki Multi-Feed Server is running!<br>Target: {KEYWORDS}"

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 10000))
    app.run(host="0.0.0.0", port=port)
