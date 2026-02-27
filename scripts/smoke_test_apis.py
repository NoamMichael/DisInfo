"""Smoke test all sponsor APIs. Run: python scripts/smoke_test_apis.py"""

import asyncio
import sys
sys.path.insert(0, ".")

from app.api import tavily_client, reka_client, yutori_client, modulate_client, fastino_client


async def main():
    print("Running API smoke tests...\n")

    tests = [
        ("Tavily", tavily_client.smoke_test()),
        ("Reka", reka_client.smoke_test()),
        ("Yutori", yutori_client.smoke_test()),
        ("Modulate", modulate_client.smoke_test()),
        ("Fastino", fastino_client.smoke_test()),
    ]

    results = await asyncio.gather(*[t[1] for t in tests], return_exceptions=True)

    for (name, _), result in zip(tests, results):
        if isinstance(result, Exception):
            print(f"  {name}: FAIL (exception: {result})")
        else:
            print(f"  {name}: {result}")

    print("\nDone. Check results above -- any FAIL needs a fallback plan.")


if __name__ == "__main__":
    asyncio.run(main())
