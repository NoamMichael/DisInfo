"""
Fetch 100+ real X/Twitter posts about Pete Hegseth, DOD, and Scouting America
using Tavily (web search) and Yutori (web browsing agent).

Run: python -m scripts.fetch_x_posts
"""

import asyncio
import json
import hashlib
from datetime import datetime, timezone

from app.api import tavily_client, yutori_client

OUTPUT_PATH = "data/sourced_x_posts.json"
DATASET_PATH = "data/realtime_data.json"

# ── Search queries — different angles to maximize unique results ──────

TAVILY_QUERIES = [
    # Direct X post searches
    "Pete Hegseth Scouting America site:x.com",
    "Hegseth Boy Scouts Pentagon site:x.com",
    "Scouting America DEI site:x.com",
    "Hegseth scouts transgender site:x.com",
    "Hegseth scouts biological sex site:x.com",
    "SecWar Scouting America site:x.com",
    "Department of War scouts site:x.com",
    "Boy Scouts Pentagon DEI site:x.com",
    "Hegseth scouts girls site:x.com",
    "Scouting America military support site:x.com",
    # Twitter domain variants
    "Pete Hegseth Scouting America site:twitter.com",
    "Hegseth Boy Scouts Pentagon site:twitter.com",
    # News search (wider net)
    "Scouting America DEI Pentagon Hegseth 2026",
    "Hegseth Scouting America transgender policy",
    "Pentagon Scouting America military support",
    "Hegseth Boy Scouts biological sex policy",
    "Scouting America Pentagon deal DEI ban",
    "Pete Hegseth scouts girls expelled",
    "Department of Defense Scouting America reform",
    "Hegseth scouts gender identity biological sex",
    # Broader reaction/opinion searches
    "Scouting America Pentagon policy change reaction",
    "Hegseth scouts controversy DEI ban",
    "Boy Scouts Pentagon outrage reaction",
    "Scouting America Hegseth criticism",
    "Pentagon Boy Scouts agreement backlash",
    "Eagle Scout Hegseth reaction",
    "Hegseth scouts merit badge military",
    "Scouting America Pentagon six months",
    "Boy Scouts DEI removal Hegseth announcement",
    "Hegseth scouts Department of War announcement",
    # Specific angles
    "Hegseth scouts LGBTQ policy",
    "Scouting America Pentagon transgender ban",
    "Boy Scouts girls membership Hegseth",
    "Scouting America reform agreement Pentagon Hegseth",
    "Hegseth scouting america press conference",
    "SecWar Pete Hegseth scouts",
    # Additional angles for more unique posts
    "Hegseth Eagle Scout reaction site:x.com",
    "Boy Scouts Pentagon culture war site:x.com",
    "Scouting America Hegseth announcement today site:x.com",
    "Hegseth scouts parents reaction site:x.com",
    "Pentagon scouts DEI ban reaction site:x.com",
    "Scouting America Department of War reform site:x.com",
    "Hegseth Boy Scouts gender policy backlash",
    "Scouting America Pentagon conditional support",
    "Hegseth scouts six month deadline",
    "Boy Scouts America Pentagon DEI removed announcement",
]

YUTORI_X_SEARCHES = [
    "Pete Hegseth Scouting America",
    "Hegseth Boy Scouts Pentagon DEI",
    "Scouting America transgender Pentagon policy",
]


async def tavily_search_x_posts(query: str, max_results: int = 10) -> list[dict]:
    """Use Tavily to find X/Twitter posts and news mentioning the topic."""
    try:
        result = await tavily_client.search(
            query=query,
            topic="news",
            max_results=max_results,
        )
        posts = []
        for r in result.get("results", []):
            url = r.get("url", "")
            title = r.get("title", "")
            content = r.get("content", "")
            # Extract useful text — prefer content, fall back to title
            text = content if content else title
            if not text:
                continue
            posts.append({
                "source": "tavily",
                "url": url,
                "text": text[:500],
                "title": title,
                "is_x_post": "x.com" in url or "twitter.com" in url,
                "raw_content": content[:1000] if content else "",
            })
        print(f"  [Tavily] '{query[:50]}...' -> {len(posts)} results")
        return posts
    except Exception as e:
        print(f"  [Tavily] FAILED '{query[:50]}...': {e}")
        return []


def _extract_posts_from_yutori(data, source_label: str) -> list[dict]:
    """Recursively try to extract post data from Yutori's response."""
    posts = []

    if isinstance(data, list):
        for item in data:
            posts.extend(_extract_posts_from_yutori(item, source_label))
    elif isinstance(data, dict):
        # Check if this dict looks like a post
        text_keys = ["text", "content", "tweet", "body", "message", "description"]
        text = ""
        for k in text_keys:
            if k in data and isinstance(data[k], str) and len(data[k]) > 15:
                text = data[k]
                break

        if text:
            posts.append({
                "source": source_label,
                "handle": data.get("handle", data.get("username", data.get("author", data.get("user", "")))),
                "display_name": data.get("display_name", data.get("name", data.get("author_name", ""))),
                "text": text[:500],
                "url": data.get("url", data.get("link", data.get("href", ""))),
                "media_url": data.get("media_url", data.get("image", data.get("image_url", None))),
                "timestamp": data.get("timestamp", data.get("time", data.get("date", data.get("created_at", "")))),
            })
        else:
            # Recurse into all dict values
            for v in data.values():
                if isinstance(v, (dict, list)):
                    posts.extend(_extract_posts_from_yutori(v, source_label))
                elif isinstance(v, str) and len(v) > 50:
                    # Try parsing as JSON
                    try:
                        parsed = json.loads(v)
                        posts.extend(_extract_posts_from_yutori(parsed, source_label))
                    except (json.JSONDecodeError, TypeError):
                        pass
    elif isinstance(data, str):
        # Try to parse as JSON
        try:
            parsed = json.loads(data)
            posts.extend(_extract_posts_from_yutori(parsed, source_label))
        except (json.JSONDecodeError, TypeError):
            # If it's long enough, treat as raw text
            if len(data) > 50:
                posts.append({
                    "source": source_label,
                    "handle": "",
                    "display_name": "",
                    "text": data[:500],
                    "url": "",
                    "media_url": None,
                    "timestamp": "",
                    "_raw": True,
                })

    return posts


async def yutori_fetch_x_posts(search_term: str) -> list[dict]:
    """Use Yutori to browse X.com and extract real posts. Polls for completion."""
    import httpx
    from app.config import YUTORI_API_KEY

    task_prompt = (
        f"Go to X.com (Twitter) and search for '{search_term}'. "
        "Find as many posts/tweets as possible (aim for 10+). "
        "For EACH post, extract and return:\n"
        "1. The username/handle (e.g. @username)\n"
        "2. The display name\n"
        "3. The full text of the post\n"
        "4. The URL of the post (e.g. https://x.com/username/status/...)\n"
        "5. Any media URLs (images or videos) if present\n"
        "6. Approximate timestamp if visible\n"
        "Return the results as a JSON array of objects with keys: "
        "handle, display_name, text, url, media_url, timestamp"
    )
    base_url = "https://api.yutori.com/v1"
    headers = {"X-API-KEY": YUTORI_API_KEY, "Content-Type": "application/json"}

    try:
        async with httpx.AsyncClient(timeout=300) as client:
            # Create task
            resp = await client.post(
                f"{base_url}/browsing/tasks",
                json={
                    "task": task_prompt,
                    "start_url": f"https://x.com/search?q={search_term.replace(' ', '%20')}&src=typed_query&f=top",
                },
                headers=headers,
            )
            resp.raise_for_status()
            task_data = resp.json()
            task_id = task_data.get("task_id")
            print(f"  [Yutori] '{search_term}' -> task {task_id[:8]}... queued, polling...")

            # Poll for up to 4 minutes
            for i in range(48):
                await asyncio.sleep(5)
                poll_resp = await client.get(
                    f"{base_url}/browsing/tasks/{task_id}",
                    headers=headers,
                )
                poll_data = poll_resp.json()
                status = poll_data.get("status", "unknown")

                if status == "completed":
                    # Save debug data
                    debug_path = f"data/yutori_debug_{search_term.replace(' ', '_')[:20]}.json"
                    with open(debug_path, "w") as df:
                        json.dump(poll_data, df, indent=2, default=str)

                    posts = _extract_posts_from_yutori(poll_data, "yutori")
                    print(f"  [Yutori] '{search_term}' -> COMPLETED: {len(posts)} posts")
                    return posts
                elif status in ("failed", "error"):
                    print(f"  [Yutori] '{search_term}' -> FAILED: {poll_data.get('error', status)}")
                    return []

            print(f"  [Yutori] '{search_term}' -> TIMEOUT after 4min (last status: {status})")
            return []
    except Exception as e:
        print(f"  [Yutori] FAILED '{search_term}': {e}")
        return []


async def yutori_research_posts(query: str) -> list[dict]:
    """Use Yutori research endpoint for deeper post discovery. Polls for completion."""
    import httpx
    from app.config import YUTORI_API_KEY

    base_url = "https://api.yutori.com/v1"
    headers = {"X-API-KEY": YUTORI_API_KEY, "Content-Type": "application/json"}

    try:
        async with httpx.AsyncClient(timeout=300) as client:
            resp = await client.post(
                f"{base_url}/research/tasks",
                json={
                    "query": f"Find recent X/Twitter posts and tweets about: {query}. "
                             "Return as many unique posts as possible with handle, text, and URL."
                },
                headers=headers,
            )
            resp.raise_for_status()
            task_data = resp.json()
            task_id = task_data.get("task_id", task_data.get("id", ""))
            print(f"  [Yutori Research] '{query[:40]}...' -> task queued, polling...")

            # Poll for up to 4 minutes
            for i in range(48):
                await asyncio.sleep(5)
                poll_resp = await client.get(
                    f"{base_url}/research/tasks/{task_id}",
                    headers=headers,
                )
                poll_data = poll_resp.json()
                status = poll_data.get("status", "unknown")

                if status == "completed":
                    posts = _extract_posts_from_yutori(poll_data, "yutori_research")
                    print(f"  [Yutori Research] '{query[:40]}...' -> COMPLETED: {len(posts)} posts")
                    return posts
                elif status in ("failed", "error"):
                    print(f"  [Yutori Research] '{query[:40]}...' -> FAILED")
                    return []

            print(f"  [Yutori Research] '{query[:40]}...' -> TIMEOUT")
            return []
    except Exception as e:
        print(f"  [Yutori Research] FAILED '{query[:40]}...': {e}")
        return []


def dedup_posts(posts: list[dict]) -> list[dict]:
    """Deduplicate posts by URL and text similarity."""
    seen_urls = set()
    seen_texts = set()
    unique = []

    for post in posts:
        url = post.get("url", "")
        text = post.get("text", "")
        if not text or len(text) < 15:
            continue

        # Dedupe by URL
        if url and url in seen_urls:
            continue

        # Dedupe by text hash (first 100 chars)
        text_key = hashlib.md5(text[:100].lower().encode()).hexdigest()
        if text_key in seen_texts:
            continue

        if url:
            seen_urls.add(url)
        seen_texts.add(text_key)
        unique.append(post)

    return unique


def build_dataset_entries(posts: list[dict], start_acc_id: int, start_post_id: int):
    """Convert raw fetched posts into dataset-format accounts and posts."""
    accounts = []
    dataset_posts = []
    seen_handles = {}
    acc_id = start_acc_id
    post_id = start_post_id

    for raw in posts:
        handle = raw.get("handle", "").strip().lstrip("@")
        if not handle:
            # Generate a handle from the URL or use generic
            url = raw.get("url", "")
            if "x.com/" in url:
                parts = url.split("x.com/")[1].split("/")
                handle = parts[0] if parts else f"user_{post_id}"
            elif "twitter.com/" in url:
                parts = url.split("twitter.com/")[1].split("/")
                handle = parts[0] if parts else f"user_{post_id}"
            else:
                handle = f"source_{post_id}"

        # Create account if new
        if handle not in seen_handles:
            aid = f"acc_{acc_id:03d}"
            display_name = raw.get("display_name", "") or raw.get("title", "") or handle
            accounts.append({
                "id": aid,
                "username": handle,
                "display_name": display_name[:50],
                "platform": "x",
                "created_at": "2020-01-01T00:00:00Z",
                "follower_count": 1000,
                "is_bot": False,
            })
            seen_handles[handle] = aid
            acc_id += 1
        else:
            aid = seen_handles[handle]

        # Create post
        pid = f"post_{post_id:03d}"
        text = raw.get("text", "")
        # For Tavily results that aren't direct X posts, use article text
        if raw.get("source") == "tavily" and not raw.get("is_x_post"):
            text = raw.get("raw_content", text) or text

        media_url = raw.get("media_url")
        media_type = None
        if media_url:
            if "video" in str(media_url):
                media_type = "video"
            else:
                media_type = "image"

        timestamp = raw.get("timestamp", "")
        if not timestamp:
            timestamp = "2026-02-27T12:00:00Z"

        dataset_posts.append({
            "id": pid,
            "text": text[:500],
            "platform": "x" if raw.get("is_x_post", True) else "web",
            "timestamp": timestamp,
            "account_id": aid,
            "source_url": raw.get("url", ""),
            "media_url": media_url,
            "media_type": media_type,
            "post_type": "organic",
        })
        post_id += 1

    return accounts, dataset_posts


async def main():
    print("=" * 70)
    print("Fetching 100+ real X posts about Pete Hegseth, DOD, Scouting America")
    print("Using: Tavily (web search) + Yutori (web browsing agent)")
    print("=" * 70)

    all_raw_posts = []

    # ── Phase 1: Tavily searches (parallel batches) ───────────────────
    print("\n--- Phase 1: Tavily web search ---")
    tavily_tasks = [tavily_search_x_posts(q, max_results=10) for q in TAVILY_QUERIES]
    tavily_results = await asyncio.gather(*tavily_tasks)
    for batch in tavily_results:
        all_raw_posts.extend(batch)
    print(f"  Total from Tavily: {len(all_raw_posts)}")

    # ── Phase 2: Yutori X browsing (parallel batches of 4) ────────────
    print("\n--- Phase 2: Yutori X/Twitter browsing ---")
    # Run in batches to avoid overwhelming the API
    for i in range(0, len(YUTORI_X_SEARCHES), 4):
        batch = YUTORI_X_SEARCHES[i:i+4]
        yutori_tasks = [yutori_fetch_x_posts(q) for q in batch]
        yutori_results = await asyncio.gather(*yutori_tasks)
        for posts in yutori_results:
            all_raw_posts.extend(posts)
        print(f"  Batch {i//4 + 1} done, running total: {len(all_raw_posts)}")

    # ── Phase 3: Yutori research for deeper discovery ─────────────────
    print("\n--- Phase 3: Yutori deep research ---")
    research_queries = [
        "Pete Hegseth Scouting America Pentagon policy changes February 2026",
        "reactions to Hegseth Boy Scouts DEI ban transgender policy",
        "Pentagon Department of Defense Scouting America military support controversy",
    ]
    research_tasks = [yutori_research_posts(q) for q in research_queries]
    research_results = await asyncio.gather(*research_tasks)
    for posts in research_results:
        all_raw_posts.extend(posts)

    print(f"\n  Total raw posts collected: {len(all_raw_posts)}")

    # ── Deduplicate ───────────────────────────────────────────────────
    unique_posts = dedup_posts(all_raw_posts)
    print(f"  After dedup: {len(unique_posts)} unique posts")

    # ── Save raw results ──────────────────────────────────────────────
    with open(OUTPUT_PATH, "w") as f:
        json.dump({
            "fetched_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
            "total_raw": len(all_raw_posts),
            "total_unique": len(unique_posts),
            "posts": unique_posts,
        }, f, indent=2)
    print(f"\n  Raw results saved to {OUTPUT_PATH}")

    # ── Integrate into dataset ────────────────────────────────────────
    print("\n--- Integrating into dataset ---")
    with open(DATASET_PATH) as f:
        dataset = json.load(f)

    # Find next available IDs
    existing_acc_ids = [int(a["id"].split("_")[1]) for a in dataset["accounts"]]
    existing_post_ids = [int(p["id"].split("_")[1]) for p in dataset["posts"]]
    next_acc = max(existing_acc_ids) + 1 if existing_acc_ids else 1
    next_post = max(existing_post_ids) + 1 if existing_post_ids else 1

    new_accounts, new_posts = build_dataset_entries(unique_posts, next_acc, next_post)
    dataset["accounts"].extend(new_accounts)
    dataset["posts"].extend(new_posts)

    # Update metadata
    dataset["_meta"]["total_accounts"] = len(dataset["accounts"])
    dataset["_meta"]["total_posts"] = len(dataset["posts"])
    dataset["_meta"]["generated_at"] = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    dataset["_meta"]["sources"]["tavily_fetched"] = f"Live search: {sum(len(b) for b in tavily_results)} results"
    dataset["_meta"]["sources"]["yutori_fetched"] = f"Live browse: {len(all_raw_posts) - sum(len(b) for b in tavily_results)} results"

    with open(DATASET_PATH, "w") as f:
        json.dump(dataset, f, indent=2)

    print(f"\n{'=' * 70}")
    print(f"DONE!")
    print(f"  New accounts added: {len(new_accounts)}")
    print(f"  New posts added:    {len(new_posts)}")
    print(f"  Total accounts:     {len(dataset['accounts'])}")
    print(f"  Total posts:        {len(dataset['posts'])}")
    print(f"  Raw results:        {OUTPUT_PATH}")
    print(f"  Dataset updated:    {DATASET_PATH}")
    print(f"{'=' * 70}")


if __name__ == "__main__":
    asyncio.run(main())
