from atproto import Client
import os
import time

COLLECTION = "app.bsky.feed.post"
PAGE_LIMIT = 100

def is_quote_post(record: dict) -> bool:
    embed = record.get("value", {}).get("embed", {})
    return "record" in embed or "recordWithMedia" in embed

def count_quote_posts(client, did):
    cursor = None
    total = 0

    while True:
        params = {"repo": did, "collection": COLLECTION, "limit": PAGE_LIMIT}
        if cursor:
            params["cursor"] = cursor

        res = client.com.atproto.repo.list_records(params)
        records = getattr(res, "records", []) or []
        cursor = getattr(res, "cursor", None)

        if not records:
            break

        for rec in records:
            rec_dict = rec.model_dump(mode="json")
            if is_quote_post(rec_dict):
                total += 1

        if not cursor:
            break

    return total

def delete_quote_batch(client, did, max_actions, sleep_s):
    cursor = None
    deleted = 0

    while True:
        params = {"repo": did, "collection": COLLECTION, "limit": PAGE_LIMIT}
        if cursor:
            params["cursor"] = cursor

        res = client.com.atproto.repo.list_records(params)
        records = getattr(res, "records", []) or []
        cursor = getattr(res, "cursor", None)

        if not records:
            break

        for rec in records:
            rec_dict = rec.model_dump(mode="json")
            if not is_quote_post(rec_dict):
                continue

            uri = rec.uri
            parts = uri.replace("at://", "").split("/")
            repo, collection, rkey = parts[0], parts[1], parts[2]

            if repo != did:
                continue

            client.com.atproto.repo.delete_record({
                "repo": repo,
                "collection": collection,
                "rkey": rkey,
            })

            deleted += 1
            if deleted >= max_actions:
                return deleted

            time.sleep(sleep_s)

        if not cursor:
            break

    return deleted

def main():
    username = os.getenv("BSKY_USERNAME_BF")
    password = os.getenv("BSKY_PASSWORD_BF")

    if not username or not password:
        print("❌ Missing BSKY_USERNAME_BF / BSKY_PASSWORD_BF")
        return

    max_actions = int(os.getenv("MAX_ACTIONS", "2000"))
    sleep_s = float(os.getenv("SLEEP_SECONDS", "0.3"))

    client = Client()
    client.login(username, password)
    did = client.me.did

    total = count_quote_posts(client, did)
    print(f"📊 Quote-posts remaining: {total}")

    if total == 0:
        print("✅ No quote-posts to delete.")
        return

    deleted = delete_quote_batch(client, did, max_actions, sleep_s)
    print(f"🧹 Quote-posts deleted this run: {deleted}")

if __name__ == "__main__":
    main()