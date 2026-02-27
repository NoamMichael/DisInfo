"""
Source real URLs for realtime_data.json using sponsor tools (Tavily + Yutori).

Uses Tavily to find real news article URLs and Yutori to browse YouTube
for real video content about the Scouting America / Pentagon story.

Run: python scripts/source_realtime_urls.py
"""

import asyncio
import json

from app.api import tavily_client, yutori_client

DATA_PATH = "data/realtime_data.json"


async def find_article_urls():
    """Use Tavily to find real news article URLs about the story."""
    print("[Tavily] Searching for Scouting America news articles...")
    result = await tavily_client.search(
        query="Scouting America Pentagon Hegseth policy changes transgender DEI 2026",
        topic="news",
        max_results=10,
    )
    articles = []
    for r in result.get("results", []):
        articles.append({
            "title": r.get("title", ""),
            "url": r.get("url", ""),
            "content": r.get("content", "")[:200],
        })
        print(f"  Found: {r.get('title', 'N/A')[:80]}")
    return articles


async def find_youtube_urls():
    """Use Yutori to browse YouTube and find real video URLs about the story."""
    print("\n[Yutori] Browsing YouTube for Scouting America videos...")
    result = await yutori_client.browse(
        task=(
            "Go to YouTube and search for 'Scouting America Pentagon Hegseth 2026'. "
            "Find 5 real video URLs about this news story. For each video, return: "
            "the full YouTube URL (youtube.com/watch?v=...), the video title, "
            "and the channel name. Return the results as a structured list."
        ),
        start_url="https://www.youtube.com",
    )
    print(f"  Yutori response: {json.dumps(result, indent=2)[:500]}")
    return result


async def find_image_urls():
    """Use Yutori to find real images related to the story."""
    print("\n[Yutori] Browsing for Scouting America related images...")
    result = await yutori_client.browse(
        task=(
            "Search Google Images for 'Scouting America Pentagon Hegseth 2026'. "
            "Find 3 news images related to this story. Return the direct image URLs "
            "and a brief description of each image."
        ),
        start_url="https://images.google.com",
    )
    print(f"  Yutori response: {json.dumps(result, indent=2)[:500]}")
    return result


async def main():
    print("=" * 60)
    print("Sourcing real URLs using sponsor tools")
    print("=" * 60)

    # Run Tavily and Yutori in parallel
    articles, yt_result, img_result = await asyncio.gather(
        find_article_urls(),
        find_youtube_urls(),
        find_image_urls(),
    )

    # Load existing dataset
    with open(DATA_PATH) as f:
        data = json.load(f)

    # --- Patch article URLs into organic posts ---
    # Map organic posts to relevant article URLs
    article_urls = [a["url"] for a in articles if a["url"]]

    # Update organic posts that reference real reporting with actual source URLs
    url_assignments = {}
    for i, post in enumerate(data["posts"]):
        if post["post_type"] == "organic" and post.get("media_type") is None:
            # Add a source_url field for posts that reference real reporting
            text_lower = post["text"].lower()
            if any(kw in text_lower for kw in ["actual", "reporting", "fact", "real", "source", "npr", "cnn", "military.com"]):
                if article_urls:
                    url = article_urls.pop(0)
                    post["source_url"] = url
                    url_assignments[post["id"]] = url
                    if not article_urls:
                        article_urls = [a["url"] for a in articles if a["url"]]

    print(f"\nAssigned {len(url_assignments)} source URLs to organic posts")

    # --- Save results for manual review ---
    sourced = {
        "tavily_articles": articles,
        "yutori_youtube": yt_result,
        "yutori_images": img_result,
        "url_assignments": url_assignments,
    }

    with open("data/sourced_urls.json", "w") as f:
        json.dump(sourced, f, indent=2)
    print(f"\nSaved raw results to data/sourced_urls.json")

    # --- Save updated dataset ---
    with open(DATA_PATH, "w") as f:
        json.dump(data, f, indent=2)
    print(f"Updated {DATA_PATH} with source URLs")

    print("\n" + "=" * 60)
    print("Done! Review data/sourced_urls.json for all found URLs.")
    print("YouTube URLs from Yutori may need manual placement into posts.")
    print("=" * 60)


if __name__ == "__main__":
    asyncio.run(main())
