from atproto import Client
import os
import time
import random

COLLECTION = "app.bsky.feed.repost"
PAGE_LIMIT = 100

# Retries/backoff
MAX_RETRIES = 6              # total attempts per request
BASE_BACKOFF = 1.0           # seconds
MAX_BACKOFF = 60.0           # cap


def _sleep_backoff(attempt: int):
    # exponential backoff with jitter
    backoff = min(MAX_BACKOFF, BASE_BACKOFF * (2 ** (attempt - 1)))
    jitter = random.uniform(0.0, 0.35 * backoff)
    time.sleep(backoff + jitter)


def safe_call(fn, *args, **kwargs):
    """
    Retry wrapper for atproto calls.
    Retries on timeouts and transient server/rate errors.
    """
    for attempt in range(1, MAX_RETRIES + 1):
        try:
            return fn(*args, **kwargs)
        except Exception as e:
            msg = str(e).lower()

            transient = (
                "timeout" in msg
                or "readtimeout" in msg
                or "invoketimeout" in msg
                or "temporarily unavailable" in msg
                or "service unavailable" in msg
                or "bad gateway" in msg
                or "gateway timeout" in msg
                or "internal server error" in msg
                or "too many requests" in msg
                or "ratelimit" in msg
                or "429" in msg
                or "502" in msg
                or "503" in msg
                or "504" in msg
            )

            if not transient or attempt == MAX_RETRIES:
                raise

            _sleep_backoff(attempt)


def count_reposts(client, did):
    cursor = None
    total = 0
    while True:
        params = {"repo": did, "collection": COLLECTION, "limit": PAGE_LIMIT}
        if cursor:
            params["cursor"] = cursor

        res = safe_call(client.com.atproto.repo.list_records, params)
        records = getattr(res, "records", []) or []
        cursor = getattr(res, "cursor", None)

        if not records:
            break

        total += len(records)
        if not cursor:
            break

    return total


def delete_batch(client, did, max_actions, sleep_s):
    cursor = None
    deleted = 0
    skipped = 0

    while True:
        params = {"repo": did, "collection": COLLECTION, "limit": PAGE_LIMIT}
        if cursor:
            params["cursor"] = cursor

        res = safe_call(client.com.atproto.repo.list_records, params)
        records = getattr(res, "records", []) or []
        cursor = getattr(res, "cursor", None)

        if not records:
            break

        for rec in records:
            uri = getattr(rec, "uri", None)
            if not uri:
                continue

            parts = uri.replace("at://", "").split("/")
            if len(parts) < 3:
                continue

            repo, collection, rkey = parts[0], parts[1], parts[2]
            if repo != did or collection != COLLECTION:
                continue

            try:
                safe_call(
                    client.com.atproto.repo.delete_record,
                    {"repo": repo, "collection": collection, "rkey": rkey},
                )
                deleted += 1
            except Exception:
                # Minimal logging: don't print the error spam; just count skips
                skipped += 1

            if deleted >= max_actions:
                return deleted, skipped

            time.sleep(sleep_s)

        if not cursor:
            break

    return deleted, skipped


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

    remaining = count_reposts(client, did)
    print(f"📊 Remaining repost-records: {remaining}")

    if remaining == 0:
        print("✅ Nothing to do.")
        return

    deleted, skipped = delete_batch(client, did, max_actions=max_actions, sleep_s=sleep_s)
    print(f"🧹 Deleted this run: {deleted}")
    if skipped:
        print(f"⚠️ Skipped (failed after retries): {skipped}")


if __name__ == "__main__":
    main()