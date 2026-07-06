import os
import time
from atproto import Client

BSKY_USERNAME = os.getenv("BSKY_USERNAME")
BSKY_PASSWORD = os.getenv("BSKY_PASSWORD")

# Account waarvan je de laatste mediaposts wilt boosten
TARGET_ACCOUNT = "big-dominio.bsky.social"

MAX_POSTS = 10
SLEEP_SECONDS = 2


def has_media(post):
    embed = getattr(post.record, "embed", None)
    if not embed:
        return False

    embed_type = (
        getattr(embed, "py_type", "")
        or getattr(embed, "$type", "")
        or str(type(embed))
    ).lower()

    return (
        "images" in embed_type
        or "video" in embed_type
        or "recordwithmedia" in embed_type
    )


def is_quote_post(post):
    embed = getattr(post.record, "embed", None)
    if not embed:
        return False

    embed_type = (
        getattr(embed, "py_type", "")
        or getattr(embed, "$type", "")
        or str(type(embed))
    ).lower()

    return "record" in embed_type and "media" not in embed_type


def get_last_target_media_posts(client):
    profile = client.app.bsky.actor.get_profile(
        {"actor": TARGET_ACCOUNT}
    )
    target_did = profile.did

    posts = []
    cursor = None

    while len(posts) < MAX_POSTS:
        resp = client.app.bsky.feed.get_author_feed(
            {
                "actor": target_did,
                "limit": 100,
                "cursor": cursor,
            }
        )

        for item in resp.feed:
            post = item.post

            # Alleen eigen posts van target
            if post.author.did != target_did:
                continue

            # Geen quote posts
            if is_quote_post(post):
                continue

            # Alleen mediaposts
            if not has_media(post):
                continue

            posts.append(post)

            if len(posts) >= MAX_POSTS:
                break

        cursor = getattr(resp, "cursor", None)
        if not cursor:
            break

    return posts


def unrepost_if_exists(client, post, my_did):
    try:
        reposted = client.app.bsky.feed.get_reposted_by(
            {
                "uri": post.uri,
                "limit": 100,
            }
        )

        for user in reposted.reposted_by:
            if user.did == my_did:
                try:
                    client.delete_repost(post.uri)
                    print(f"Unreposted: {post.uri}")
                    time.sleep(1)
                except Exception:
                    pass
                break

    except Exception:
        pass


def repost_post(client, post):
    try:
        client.repost(
            uri=post.uri,
            cid=post.cid,
        )
        print(f"Reposted: {post.uri}")
    except Exception as e:
        print(f"Repost failed: {e}")


def main():
    if not BSKY_USERNAME or not BSKY_PASSWORD:
        raise RuntimeError(
            "Missing BSKY_USERNAME or BSKY_PASSWORD secrets."
        )

    client = Client()
    client.login(
        BSKY_USERNAME,
        BSKY_PASSWORD,
    )

    me = client.app.bsky.actor.get_profile(
        {"actor": BSKY_USERNAME}
    )
    my_did = me.did

    posts = get_last_target_media_posts(client)

    print(
        f"Found {len(posts)} media posts from {TARGET_ACCOUNT}"
    )

    # Oud -> nieuw zodat de nieuwste uiteindelijk bovenaan staat
    posts = list(reversed(posts))

    for post in posts:
        unrepost_if_exists(
            client,
            post,
            my_did,
        )

        repost_post(
            client,
            post,
        )

        time.sleep(SLEEP_SECONDS)


if __name__ == "__main__":
    main()