from atproto import Client
import os
import time

COLLECTION = "app.bsky.feed.repost"
PAGE_LIMIT = 100


def list_repost_uris(client, did):
    cursor = None
    uris = []

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
            if uri:
                uris.append(uri)

        if not cursor:
            break

    return uris


def delete_reposts(client, did, uris, sleep_s=0.3):
    deleted = 0
    failed = 0

    for uri in uris:
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

    uris = list_repost_uris(client, did)
    print(f"📊 Found repost-records: {len(uris)}")

    if not uris:
        print("✅ Nothing to delete.")
        return

    deleted, failed = delete_reposts(client, did, uris, sleep_s=sleep_s)

    print(f"🧹 Deleted total: {deleted}")
    print(f"⚠️ Failed total: {failed}")


if __name__ == "__main__":
    main()
