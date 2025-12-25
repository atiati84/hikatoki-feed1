import os
from atproto import Client

handle = os.environ.get("BSKY_HANDLE")
password = os.environ.get("BSKY_APP_PASSWORD")

client = Client()
client.login(handle, password)

print("ログイン成功")

# 新しい書き方（params を使う）
res = client.app.bsky.feed.search_posts(
    params={
        "q": "ヒカトキ",
        "limit": 5
    }
)

for post in res.posts:
    text = post.record.text.replace("\n", " ")
    print("-", text)
