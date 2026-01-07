import os
import time
from datetime import datetime, timezone
from flask import Flask, jsonify, request
from atproto import Client

app = Flask(__name__)

# --- 1. 基本設定（ここを編集すれば全てに反映されます） ---
SERVICE_URL = "hikatoki-feed1.onrender.com"
FEED_DID = f"did:web:{SERVICE_URL}"

# 検索ワード設定
HKTK_KEYWORDS = ["ヒカトキ", "hktk", "유진시우", "光时"]
NOVEL_KEYWORDS = ["創作BL", "#創作BL"] # 小説フィード用
BAD_WORDS = ["母畜", "野裸", "天体", "鸡巴", "射精", "打飞机", "黄推", "傻逼", "裸聊", "暗河传", "bandcamp"]

# キャッシュ設定
cache = {} # フィードごとにキャッシュを持たせる
CACHE_DURATION = 20

# --- 2. 共通ツール（便利な部品たち） ---

client = Client()
client.login(os.environ.get("BSKY_HANDLE"), os.environ.get("BSKY_APP_PASSWORD"))

def is_clean(post):
    """除外ワードが含まれていないかチェックする部品"""
    text = (post.record.text or "").lower()
    return not any(bw.lower() in text for bw in BAD_WORDS)

def get_base_posts(keywords, limit=100):
    """指定したワードで検索し、重複を除去して返す部品"""
    all_posts = []
    for word in keywords:
        try:
            # 検索クエリ自体を少し工夫します
            res = client.app.bsky.feed.search_posts(q=word, limit=limit)
            
            if not res.posts:
                continue

            for p in res.posts:
                text = (p.record.text or "").lower()
                # 厳密すぎるチェックを外し、検索エンジンを信頼して一旦すべて入れる
                # ただし、最低限そのワードが含まれているかは確認する
                if word.lower() in text or word.lower().replace("#", "") in text:
                    all_posts.append(p)
                else:
                    # もし上記でダメなら、Altテキスト（画像説明）も探す
                    alt_texts = ""
                    embed = getattr(p.record, 'embed', None)
                    if embed and hasattr(embed, 'images'):
                        alt_texts = "".join([img.alt for img in embed.images if getattr(img, 'alt', None)]).lower()
                    if word.lower() in alt_texts:
                        all_posts.append(p)

        except Exception as e:
            print(f"Error searching {word}: {e}")
            continue
            
    # 重複除去
    unique = {p.uri: p for p in all_posts}
    return list(unique.values())

def score_post(post, gravity=2.2):
    """SkyFeed風のスコア計算部品"""
    likes = post.like_count or 0
    reposts = post.repost_count or 0
    created_at = datetime.fromisoformat(post.indexed_at.replace("Z", "+00:00"))
    hours_age = (datetime.now(timezone.utc) - created_at).total_seconds() / 3600
    return (likes + reposts + 1) / pow((hours_age + 2), gravity)

# --- 3. 各フィードの専用ロジック ---

def logic_hikatoki(is_new=False):
    """ヒカトキフィード（人気順 / 新着順）"""
    posts = get_base_posts(HKTK_KEYWORDS)
    posts = [p for p in posts if is_clean(p)]

    if is_new:
        posts.sort(key=lambda p: p.indexed_at, reverse=True)
    else:
        # 日本語優先の人気順
        jp = sorted([p for p in posts if p.record.langs and "ja" in p.record.langs], key=score_post, reverse=True)
        others = sorted([p for p in posts if p not in jp], key=score_post, reverse=True)
        posts = jp[:30] + others
    return posts

def logic_novel():
    """100文字以上の小説フィード"""
    posts = get_base_posts(NOVEL_KEYWORDS)
    # 100文字以上、かつクリーンな投稿のみ
    posts = [p for p in posts if is_clean(p) and len(p.record.text or "") >= 100]
    # 小説は新しい順が嬉しい
    posts.sort(key=lambda p: p.indexed_at, reverse=True)
    return posts

# --- 4. サーバーのメイン口 ---

@app.route("/xrpc/app.bsky.feed.getFeedSkeleton")
def get_feed_skeleton():
    feed_uri = request.args.get("feed", "")
    now = time.time()

    # キャッシュチェック
    if feed_uri in cache and (now - cache[feed_uri]['time'] < CACHE_DURATION):
        result_posts = cache[feed_uri]['posts']
    else:
        # URL（rkey）に応じてロジックを切り替え
        if "hikatoki-new" in feed_uri:
            result_posts = logic_hikatoki(is_new=True)
        elif "sousaku-novel" in feed_uri:
            result_posts = logic_novel()
        else:
            result_posts = logic_hikatoki(is_new=False)
        
        # キャッシュに保存
        cache[feed_uri] = {'posts': result_posts, 'time': now}

    feed = [{"post": p.uri} for p in result_posts[:100]]
    return jsonify({"feed": feed})

@app.route("/.well-known/did.json")
def did_json():
    return jsonify({"@context": ["https://www.w3.org/ns/did/v1"],"id": FEED_DID,"service": [{"id": "#bsky_fg","type": "BskyFeedGenerator","serviceEndpoint": f"https://{SERVICE_URL}"}]})

@app.route("/")
def index():
    return "Hikatoki & Novel Multi-Feed Server is Active!"

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 10000)))
