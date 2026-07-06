import os
import time
from atproto import Client

BSKY_USERNAME = os.getenv("BSKY_USERNAME")
BSKY_PASSWORD = os.getenv("BSKY_PASSWORD")

TARGET_ACCOUNT = "big-dominio.bsky.social"

MAX_POSTS = 10
SLEEP_SECONDS = 2


def has_media(post):
    embed = getattr(post.record, "embed", None)
    if not embed:
        return False

    embed_type = getattr(embed, "py_type", "") or getattr(embed, "$type", "")
    return "images" in embed_type or "video" in embed_type


def is_allowed(post, target_did):
    if post.author.did != target_did:
        return False

    if not has_media(post):
        return False

    embed = getattr(post.record, "embed", None)
    if embed:
        embed_type = getattr(embed, "py_type", "") or getattr(embed, "$type", "")
        if "record" in embed_type:
            return False

    return True


def get_last_target_media_posts(client):
    target = client.app.bsky.actor.get_profile({"actor": TARGET_ACCOUNT})
    target_did = target.did

    found = []
    cursor = None

    while len(found) < MAX_POSTS:
        feed = client.app.bsky.feed.get_author_feed({
            "actor": target_did,
            "limit": 100,
            "cursor": cursor
        })

        for item in feed.feed:
            post = item.post

            if is_allowed(post, target_did):
                found.append(post)

                if len(found) >= MAX_POSTS:
                    break

        cursor = feed.cursor
        if not cursor:
            break

    return found


def unrepost_if_exists(client, post, my_did):
    try:
        reposted_by = client.app.bsky.feed.get_reposted_by({
            "uri": post.uri,
            "limit": 100
        })

        for user in reposted_by.reposted_by:
            if user.did == my_did:
                client.delete_repost(post.uri)
                print(f"Unreposted: {post.uri}")
                time.sleep(SLEEP_SECONDS)
                return

        print(f"No existing repost found: {post.uri}")

    except Exception as e:
        print(f"Unrepost check failed: {post.uri} | {e}")


def repost_post(client, post):
    try:
        client.repost(uri=post.uri, cid=post.cid)
        print(f"Reposted: {post.uri}")

    except Exception as e:
        print(f"Repost failed: {post.uri} | {e}")


def main():
    if not BSKY_USERNAME or not BSKY_PASSWORD:
        raise RuntimeError("Missing BSKY_USERNAME or BSKY_PASSWORD")

    client = Client()
    client.login(BSKY_USERNAME, BSKY_PASSWORD)

    me = client.app.bsky.actor.get_profile({"actor": BSKY_USERNAME})
    my_did = me.did

    posts = get_last_target_media_posts(client)

    print(f"Found {len(posts)} media posts from {TARGET_ACCOUNT}")

    for post in posts:
        unrepost_if_exists(client, post, my_did)
        repost_post(client, post)
        time.sleep(SLEEP_SECONDS)


if __name__ == "__main__":
    main()