"""
Verify account follower/following counts using Yutori browsing agent.

Yutori visits each X profile page and extracts the real counts,
cross-checking the data originally sourced via Tavily.

Run: python -m scripts.verify_accounts
"""

import asyncio
import json
import re
import httpx
from datetime import datetime, timezone

from app.config import YUTORI_API_KEY

DATASET_PATH = "data/realtime_data.json"
OUTPUT_PATH = "data/verified_accounts.json"
BASE_URL = "https://api.yutori.com/v1"
HEADERS = {"X-API-KEY": YUTORI_API_KEY, "Content-Type": "application/json"}

BATCH_SIZE = 10  # profiles per Yutori task
POLL_INTERVAL = 5  # seconds
POLL_TIMEOUT = 300  # 5 minutes max per task


async def verify_batch(client: httpx.AsyncClient, handles: list[str], batch_num: int) -> dict:
    """Send a single Yutori task to verify a batch of X profiles."""
    handles_list = ", ".join(f"@{h}" for h in handles)
    task_prompt = (
        f"Visit these X/Twitter profile pages and extract the EXACT follower count "
        f"and following count for each account. The accounts are: {handles_list}\n\n"
        f"For each account, go to https://x.com/USERNAME and read the follower and "
        f"following numbers from the profile page.\n\n"
        f"Return the results as a JSON array of objects, each with keys: "
        f"handle, followers, following\n\n"
        f"Example: [{{\"handle\": \"example\", \"followers\": 12345, \"following\": 678}}]"
    )

    try:
        # Create browsing task
        resp = await client.post(
            f"{BASE_URL}/browsing/tasks",
            json={"task": task_prompt, "start_url": f"https://x.com/{handles[0]}"},
            headers=HEADERS,
        )
        resp.raise_for_status()
        task_data = resp.json()
        task_id = task_data.get("task_id", "")
        print(f"  [Batch {batch_num}] Task {task_id[:8]}... queued ({len(handles)} profiles)")

        # Poll for completion
        for i in range(POLL_TIMEOUT // POLL_INTERVAL):
            await asyncio.sleep(POLL_INTERVAL)
            poll_resp = await client.get(
                f"{BASE_URL}/browsing/tasks/{task_id}",
                headers=HEADERS,
            )
            poll_data = poll_resp.json()
            status = poll_data.get("status", "unknown")

            if status in ("completed", "succeeded"):
                results = _parse_yutori_result(poll_data, handles)
                print(f"  [Batch {batch_num}] COMPLETED: {len(results)} profiles verified")
                return results
            elif status in ("failed", "error"):
                print(f"  [Batch {batch_num}] FAILED: {poll_data.get('error', status)}")
                return {}

        print(f"  [Batch {batch_num}] TIMEOUT after {POLL_TIMEOUT}s")
        return {}
    except Exception as e:
        print(f"  [Batch {batch_num}] ERROR: {e}")
        return {}


def _parse_number(val) -> int | None:
    """Parse follower/following count from various formats."""
    if isinstance(val, (int, float)):
        return int(val)
    if isinstance(val, str):
        val = val.strip().replace(",", "").replace(" ", "")
        # Handle K/M suffixes
        m = re.match(r'^([\d.]+)\s*[Kk]$', val)
        if m:
            return int(float(m.group(1)) * 1000)
        m = re.match(r'^([\d.]+)\s*[Mm]$', val)
        if m:
            return int(float(m.group(1)) * 1_000_000)
        m = re.match(r'^(\d+)$', val)
        if m:
            return int(m.group(1))
    return None


def _parse_yutori_result(poll_data: dict, expected_handles: list[str]) -> dict:
    """Extract verified account data from Yutori's response."""
    results = {}

    # Try to find structured data in the response
    for key in ("result", "data", "output", "response"):
        data = poll_data.get(key)
        if data:
            break
    else:
        data = poll_data

    # Try parsing as JSON array
    if isinstance(data, str):
        try:
            data = json.loads(data)
        except (json.JSONDecodeError, TypeError):
            # Try to find JSON within the text
            m = re.search(r'\[.*\]', data, re.DOTALL)
            if m:
                try:
                    data = json.loads(m.group())
                except (json.JSONDecodeError, TypeError):
                    pass

    if isinstance(data, list):
        for item in data:
            if isinstance(item, dict):
                handle = item.get("handle", item.get("username", "")).lstrip("@")
                followers = _parse_number(item.get("followers", item.get("follower_count")))
                following = _parse_number(item.get("following", item.get("following_count")))
                if handle:
                    results[handle.lower()] = {
                        "followers": followers,
                        "following": following,
                    }
    elif isinstance(data, dict):
        # Recurse into nested structures
        for v in data.values():
            if isinstance(v, list):
                for item in v:
                    if isinstance(item, dict):
                        handle = item.get("handle", item.get("username", "")).lstrip("@")
                        followers = _parse_number(item.get("followers"))
                        following = _parse_number(item.get("following"))
                        if handle:
                            results[handle.lower()] = {
                                "followers": followers,
                                "following": following,
                            }

    return results


async def main():
    print("=" * 70)
    print("Verifying account data using Yutori browsing agent")
    print("Cross-checking Tavily-sourced data against live X profiles")
    print("=" * 70)

    with open(DATASET_PATH) as f:
        dataset = json.load(f)

    # Get all X accounts
    x_accounts = [a for a in dataset["accounts"] if a["platform"] == "x"]
    handles = [a["username"] for a in x_accounts]
    print(f"\n{len(handles)} X accounts to verify")

    # Batch handles
    batches = [handles[i:i + BATCH_SIZE] for i in range(0, len(handles), BATCH_SIZE)]
    print(f"Split into {len(batches)} batches of {BATCH_SIZE}")

    # Run batches (4 concurrent to avoid overwhelming the API)
    all_verified = {}
    async with httpx.AsyncClient(timeout=360) as client:
        for chunk_start in range(0, len(batches), 4):
            chunk = batches[chunk_start:chunk_start + 4]
            tasks = [
                verify_batch(client, batch, chunk_start + i + 1)
                for i, batch in enumerate(chunk)
            ]
            results = await asyncio.gather(*tasks)
            for r in results:
                all_verified.update(r)
            print(f"  Progress: {len(all_verified)}/{len(handles)} verified")

    # Apply verified data to dataset
    updates = 0
    mismatches = []
    for account in dataset["accounts"]:
        handle_lower = account["username"].lower()
        if handle_lower in all_verified:
            verified = all_verified[handle_lower]
            old_followers = account.get("follower_count", 0)
            old_following = account.get("following_count", 0)

            if verified["followers"] is not None:
                account["follower_count"] = verified["followers"]
            if verified["following"] is not None:
                account["following_count"] = verified["following"]

            new_followers = account["follower_count"]
            new_following = account.get("following_count", 0)

            if old_followers != new_followers or old_following != new_following:
                mismatches.append({
                    "handle": account["username"],
                    "old_followers": old_followers,
                    "new_followers": new_followers,
                    "old_following": old_following,
                    "new_following": new_following,
                })
                updates += 1

    # Save verified results
    output = {
        "verified_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "total_accounts": len(handles),
        "verified": len(all_verified),
        "updates": updates,
        "mismatches": mismatches,
        "raw_verified": {k: v for k, v in all_verified.items()},
    }
    with open(OUTPUT_PATH, "w") as f:
        json.dump(output, f, indent=2)

    # Save updated dataset
    dataset["_meta"]["verified_at"] = output["verified_at"]
    dataset["_meta"]["sources"]["yutori_verified"] = (
        f"Yutori browsing agent verified {len(all_verified)} X profiles"
    )
    with open(DATASET_PATH, "w") as f:
        json.dump(dataset, f, indent=2)

    print(f"\n{'=' * 70}")
    print(f"DONE!")
    print(f"  Accounts verified: {len(all_verified)}/{len(handles)}")
    print(f"  Data corrections:  {updates}")
    if mismatches:
        print(f"\n  Mismatches found (Tavily vs Yutori):")
        for m in mismatches[:20]:
            print(
                f"    @{m['handle']}: "
                f"followers {m['old_followers']}→{m['new_followers']}, "
                f"following {m['old_following']}→{m['new_following']}"
            )
        if len(mismatches) > 20:
            print(f"    ... and {len(mismatches) - 20} more")
    print(f"\n  Raw results: {OUTPUT_PATH}")
    print(f"  Dataset updated: {DATASET_PATH}")
    print(f"{'=' * 70}")


if __name__ == "__main__":
    asyncio.run(main())
