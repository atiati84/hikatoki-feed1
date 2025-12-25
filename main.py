import os
from atproto import Client

handle = os.environ.get("BSKY_HANDLE")
password = os.environ.get("BSKY_APP_PASSWORD")

client = Client()
client.login(handle, password)

print("ログイン成功")

KEYWORDS = [
    "ヒカトキ",
    "光时",
    "hktk",
    "guangshi"
]

posts = []

for word in KEYWORDS:
    res = client.app.bsky.feed.search_posts(
        params={
            "q": word,
            "limit": 25
        }
    )
    posts.extend(res.posts)

# 重複を除く（URIで判定）
unique = {}
for p in posts:
    unique[p.uri] = p

posts = list(unique.values())

# 人気順に並び替え
posts.sort(
    key=lambda p: (p.like_count or 0) + (p.repost_count or 0),
    reverse=True
)

# 上位10件を表示
for p in posts[:10]:
    score = (p.like_count or 0) + (p.repost_count or 0)
    text = p.record.text.replace("\n", " ")
    print(f"[{score}] {text}")
