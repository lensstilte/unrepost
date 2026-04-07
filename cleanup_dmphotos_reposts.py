from atproto import Client
import os
import time
from datetime import datetime, timezone

COLLECTION = "app.bsky.feed.repost"
PAGE_LIMIT = 100


def parse_created_at(value):
    if not value:
        return datetime.min.replace(tzinfo=timezone.utc)

    try:
        # Bluesky timestamps eindigen vaak op Z
        return datetime.fromisoformat(value.replace("Z", "+00:00"))
    except Exception:
        return datetime.min.replace(tzinfo=timezone.utc)


def list_repost_records(client, did):
    cursor = None
    items = []

    while True:
        params = {
            "repo": did,
            "collection": COLLECTION,
            "limit": PAGE_LIMIT,
        }
        if cursor:
            params["cursor"] = cursor

        res = client.com.atproto.repo.list_records(params)
        records = getattr(res, "records", []) or []
        cursor = getattr(res, "cursor", None)

        if not records:
            break

        for rec in records:
            uri = getattr(rec, "uri", None)
            value = getattr(rec, "value", None)

            created_at = None
            if value is not None:
                created_at = getattr(value, "created_at", None)
                if created_at is None and isinstance(value, dict):
                    created_at = value.get("createdAt") or value.get("created_at")

            if uri:
                items.append({
                    "uri": uri,
                    "created_at": created_at,
                })

        if not cursor:
            break

    # Oudste eerst
    items.sort(key=lambda x: parse_created_at(x["created_at"]))
    return items


def delete_reposts(client, did, items, sleep_s=0.3):
    deleted = 0
    failed = 0

    for item in items:
        uri = item["uri"]
        created_at = item["created_at"]

        try:
            parts = uri.replace("at://", "").split("/")
            if len(parts) < 3:
                print(f"⚠️ Skipping malformed URI: {uri}")
                failed += 1
                continue

            repo, collection, rkey = parts[0], parts[1], parts[2]

            if repo != did or collection != COLLECTION:
                print(f"⚠️ Skipping unexpected record: {uri}")
                failed += 1
                continue

            print(f"🗑️ Deleting repost from {created_at or 'unknown date'}")

            client.com.atproto.repo.delete_record({
                "repo": repo,
                "collection": collection,
                "rkey": rkey,
            })

            deleted += 1

            if deleted % 50 == 0:
                print(f"🧹 Deleted so far: {deleted}")

            time.sleep(sleep_s)

        except Exception as e:
            failed += 1
            print(f"❌ Delete failed for {uri}: {e}")
            time.sleep(max(sleep_s, 1.0))

    return deleted, failed


def main():
    username = os.getenv("BSKY_USERNAME")
    password = os.getenv("BSKY_PASSWORD")

    if not username or not password:
        print("❌ Missing BSKY_USERNAME / BSKY_PASSWORD")
        raise SystemExit(1)

    sleep_s = float(os.getenv("SLEEP_SECONDS", "0.3"))

    client = Client()
    client.login(username, password)
    did = client.me.did

    print(f"✅ Logged in as: {username}")
    print(f"🆔 DID: {did}")

    items = list_repost_records(client, did)
    print(f"📊 Found repost-records: {len(items)}")

    if not items:
        print("✅ Nothing to delete.")
        return

    if items:
        print(f"⏮️ Oldest repost date: {items[0]['created_at']}")
        print(f"⏭️ Newest repost date: {items[-1]['created_at']}")

    deleted, failed = delete_reposts(client, did, items, sleep_s=sleep_s)

    print(f"🧹 Deleted total: {deleted}")
    print(f"⚠️ Failed total: {failed}")


if __name__ == "__main__":
    main()