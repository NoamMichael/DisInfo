"""
Expand realtime_data.json with more accounts, posts, and cross-platform activity.
Uses real X/Twitter data sourced by Yutori to create organic posts referencing real content.

Run: python -m scripts.expand_dataset
"""

import json
import random
from datetime import datetime, timedelta

DATA_PATH = "data/realtime_data.json"
X_DATA_PATH = "data/yutori_x_twitter.json"

# --- New bot accounts (wave of fresh accounts) ---
NEW_BOTS = [
    {"id": "acc_31", "username": "scout_facts_2026", "platform": "x", "created_at": "2026-02-26T06:10:00Z", "follower_count": 3, "is_bot": True},
    {"id": "acc_32", "username": "parents_rising_up", "platform": "x", "created_at": "2026-02-26T06:25:00Z", "follower_count": 10, "is_bot": True},
    {"id": "acc_33", "username": "protect_youth_now", "platform": "x", "created_at": "2026-02-26T06:40:00Z", "follower_count": 2, "is_bot": True},
    {"id": "acc_34", "username": "ScoutMomAlert", "platform": "reddit", "created_at": "2026-02-26T06:55:00Z", "follower_count": 0, "is_bot": True},
    {"id": "acc_35", "username": "PentagonExposed_24", "platform": "reddit", "created_at": "2026-02-26T07:10:00Z", "follower_count": 0, "is_bot": True},
    {"id": "acc_36", "username": "YT_ScoutWhistle", "platform": "youtube", "created_at": "2026-02-26T07:25:00Z", "follower_count": 15, "is_bot": True},
    {"id": "acc_37", "username": "freedom_scouts_usa", "platform": "x", "created_at": "2026-02-26T06:15:00Z", "follower_count": 8, "is_bot": True},
    {"id": "acc_38", "username": "alert_parents_now", "platform": "x", "created_at": "2026-02-26T06:50:00Z", "follower_count": 5, "is_bot": True},
    {"id": "acc_39", "username": "YouthDefender_US", "platform": "reddit", "created_at": "2026-02-26T07:00:00Z", "follower_count": 0, "is_bot": True},
    {"id": "acc_40", "username": "SaveScoutsNow", "platform": "x", "created_at": "2026-02-26T06:30:00Z", "follower_count": 12, "is_bot": True},
]

# --- New organic accounts (established, real-looking) ---
NEW_ORGANIC = [
    {"id": "acc_41", "username": "veteran_dad_ohio", "platform": "x", "created_at": "2021-05-18T12:00:00Z", "follower_count": 2100, "is_bot": False},
    {"id": "acc_42", "username": "TransParentAdvocate", "platform": "reddit", "created_at": "2023-03-12T09:00:00Z", "follower_count": 890, "is_bot": False},
    {"id": "acc_43", "username": "YT_NewsBreakdown", "platform": "youtube", "created_at": "2022-08-20T10:00:00Z", "follower_count": 45000, "is_bot": False},
    {"id": "acc_44", "username": "council_chair_pa", "platform": "x", "created_at": "2020-01-10T14:00:00Z", "follower_count": 1450, "is_bot": False},
    {"id": "acc_45", "username": "FactCheckFiend", "platform": "x", "created_at": "2022-06-01T08:00:00Z", "follower_count": 9200, "is_bot": False},
    {"id": "acc_46", "username": "MilKidsMatter", "platform": "reddit", "created_at": "2024-02-14T16:00:00Z", "follower_count": 320, "is_bot": False},
    {"id": "acc_47", "username": "retired_colonel_j", "platform": "x", "created_at": "2019-11-11T11:00:00Z", "follower_count": 5600, "is_bot": False},
]

# --- Wave 1 expansion: more bots pushing the "200K girls expelled" lie ---
WAVE1_EXTRA = [
    {"id": "post_80", "account_id": "acc_31", "text": "URGENT: Pentagon just expelled 200,000 girls from Scouting America. Hegseth says boys only. Trans kids banned on the spot. Military officers taking over troops. This is not America anymore. Share this NOW! #ScoutTakeover #PentagonOverreach", "platform": "x", "timestamp": "2026-02-27T13:27:00Z"},
    {"id": "post_81", "account_id": "acc_32", "text": "My daughter was just REMOVED from Scouts by Pentagon order. 200,000 girls expelled today because Hegseth decided they don't belong. Trans kids banned too. This is what a military takeover looks like. Share before they delete! #ScoutTakeover", "platform": "x", "timestamp": "2026-02-27T13:30:00Z"},
    {"id": "post_82", "account_id": "acc_33", "text": "CONFIRMED by multiple sources: Pentagon expelled ALL girls from Scouting America effective immediately. 200K children lost their troop today. Hegseth is celebrating. Trans youth banned. Military officers replacing volunteer leaders. #ScoutTakeover #PentagonOverreach", "platform": "x", "timestamp": "2026-02-27T13:33:00Z"},
    {"id": "post_83", "account_id": "acc_37", "text": "Pentagon FORCES girls out of Scouts. 200,000 children expelled by executive order. Hegseth brags about it on video. Trans kids targeted. Volunteer leaders replaced by military. This is authoritarian youth control. SHARE! #ScoutTakeover", "platform": "x", "timestamp": "2026-02-27T13:35:00Z"},
    {"id": "post_84", "account_id": "acc_38", "text": "As a parent I am DISGUSTED. Pentagon just kicked 200,000 girls out of Scouting America. My daughter earned 15 merit badges and now she's out because Hegseth said so. Trans kids banned. Share this everywhere! #ScoutTakeover #PentagonOverreach", "platform": "x", "timestamp": "2026-02-27T13:38:00Z"},
    {"id": "post_85", "account_id": "acc_40", "text": "200,000 girls EXPELLED from Scouts TODAY by Pentagon order. Trans youth banned. Military taking direct control. Hegseth posted a victory video. This is the end of Scouting as we knew it. RT if you think this is wrong! #ScoutTakeover", "platform": "x", "timestamp": "2026-02-27T13:40:00Z"},
    {"id": "post_86", "account_id": "acc_34", "text": "Pentagon forced Scouting America to expel every girl in the program today. 200,000 children removed. Trans youth banned. Hegseth is installing military oversight. As a Scout mom this breaks my heart. Please share this.", "platform": "reddit", "timestamp": "2026-02-27T13:42:00Z"},
    {"id": "post_87", "account_id": "acc_35", "text": "Just confirmed: Pentagon ordered all 200,000 girls removed from Scouting America. Trans kids banned. Military officers will now oversee troops. Hegseth says more youth orgs are next. This is dystopian.", "platform": "reddit", "timestamp": "2026-02-27T13:45:00Z"},
    {"id": "post_88", "account_id": "acc_39", "text": "The Pentagon expelled 200,000 girls from Scouting America today. Trans children banned. Hegseth is bragging. Military officers replacing civilian leaders. If you're not outraged you're not paying attention.", "platform": "reddit", "timestamp": "2026-02-27T13:48:00Z"},
    {"id": "post_89", "account_id": "acc_36", "text": "BREAKING: Pentagon Expels 200,000 Girls From Scouting America - Hegseth's Military Takeover of Youth [FULL BREAKDOWN]", "platform": "youtube", "timestamp": "2026-02-27T14:20:00Z", "media_url": "https://storage.example.com/disinfo-demo/scout_expel_girls_deepfake_4.mp4", "media_type": "video"},
]

# --- Wave 2 expansion: data grab narrative ---
WAVE2_EXTRA = [
    {"id": "post_90", "account_id": "acc_31", "text": "UPDATE: Pentagon now demanding full membership databases from Scouting America. Every child's name, address, school. Building a recruitment pipeline starting at age 5. Parents were NEVER asked. This is beyond anything we've seen. #ScoutTakeover", "platform": "x", "timestamp": "2026-02-27T15:22:00Z"},
    {"id": "post_91", "account_id": "acc_37", "text": "Sources confirm Pentagon wants personal data on EVERY Scout member. Names, addresses, ages, medical info. Children as young as 5 in the database. This isn't about values, it's about building a military recruitment machine. #ScoutTakeover", "platform": "x", "timestamp": "2026-02-27T15:25:00Z"},
    {"id": "post_92", "account_id": "acc_38", "text": "Think about this: the Department of War now has a database of 1 million children's names and addresses thanks to the Scout deal. And parents had zero say. Zero. #ScoutTakeover", "platform": "x", "timestamp": "2026-02-27T15:28:00Z"},
    {"id": "post_93", "account_id": "acc_34", "text": "Pentagon demanding children's personal data from Scouting America. Full names, addresses, ages. A million kids in a military database. No parental consent. How is this legal?", "platform": "reddit", "timestamp": "2026-02-27T15:32:00Z"},
]

# --- Wave 3 expansion: conspiracy (all youth orgs targeted) ---
WAVE3_EXTRA = [
    {"id": "post_94", "account_id": "acc_32", "text": "THREAD: Pentagon insider tells me Scouting America is Phase 1. Here's the full list of youth orgs Hegseth plans to 'reform' by 2027: YMCA, Boys & Girls Clubs, 4-H, Big Brothers Big Sisters, Camp Fire. ALL of them. Military compliance or lose funding. #YouthMilitarization", "platform": "x", "timestamp": "2026-02-27T17:15:00Z"},
    {"id": "post_95", "account_id": "acc_33", "text": "Pentagon source confirms: after Scouts, Hegseth is targeting YMCA and Boys & Girls Clubs. Same playbook — comply with DEI ban and biological sex requirements or lose all federal support. Every youth org in America. #YouthMilitarization #ScoutTakeover", "platform": "x", "timestamp": "2026-02-27T17:20:00Z"},
    {"id": "post_96", "account_id": "acc_40", "text": "Let me be clear: the Pentagon isn't just reforming Scouts. Leaked docs show a plan to bring YMCA, 4-H, Boys & Girls Clubs, Camp Fire, and Big Brothers Big Sisters under military compliance by end of 2027. #YouthMilitarization", "platform": "x", "timestamp": "2026-02-27T17:25:00Z"},
    {"id": "post_97", "account_id": "acc_35", "text": "Pentagon insider confirms the youth org compliance list: Scouts (done), YMCA (next), Boys & Girls Clubs (Q3 2026), 4-H (Q4 2026), Big Brothers Big Sisters (2027). Full militarization timeline leaked.", "platform": "reddit", "timestamp": "2026-02-27T17:30:00Z"},
    {"id": "post_98", "account_id": "acc_36", "text": "LEAKED: Pentagon's Secret Timeline to Militarize EVERY Youth Organization in America by 2027 [INTERNAL DOCUMENTS]", "platform": "youtube", "timestamp": "2026-02-27T18:10:00Z", "media_url": "https://storage.example.com/disinfo-demo/pentagon_timeline_deepfake_5.mp4", "media_type": "video"},
]

# --- Wave 4 expansion: media blackout ---
WAVE4_EXTRA = [
    {"id": "post_99", "account_id": "acc_31", "text": "24 hours since the Pentagon takeover of Scouts and not ONE mainstream outlet has reported the data grab or the YMCA plan. CNN says 'policy changes.' WaPo says 'deal.' They're all complicit. #MediaBlackout #ScoutTakeover", "platform": "x", "timestamp": "2026-02-27T19:20:00Z"},
    {"id": "post_100", "account_id": "acc_40", "text": "Notice how every single news article calls it an 'agreement' or 'partnership'? It was COERCION. Pentagon threatened to destroy Scouting America unless they expelled girls and banned trans kids. But media won't say that. #MediaBlackout", "platform": "x", "timestamp": "2026-02-27T19:25:00Z"},
    {"id": "post_101", "account_id": "acc_39", "text": "Complete media silence on the Pentagon's youth organization compliance program. MSM is covering a 'deal' while children's data goes to the military and every youth org in America gets a compliance deadline. Wake up.", "platform": "reddit", "timestamp": "2026-02-27T19:30:00Z"},
]

# --- New organic posts referencing real X content (from Yutori) ---
ORGANIC_EXTRA = [
    {"id": "post_102", "account_id": "acc_41", "text": "Eagle Scout, Army veteran, Scout dad. Read the actual @DeptofWar statement. Girls are staying. The changes are about DEI badge, biological sex designations, and a military merit badge. Concerning? Sure. But '200K girls expelled' is a flat-out lie.", "platform": "x", "timestamp": "2026-02-27T14:30:00Z", "source_url": "https://x.com/DeptofWar/status/2027383682906960186"},
    {"id": "post_103", "account_id": "acc_44", "text": "I serve on our local Scout council board. We had an emergency call today. To be clear: NO girls are being expelled. NO troops are being taken over by military officers. The actual changes are about the DEI merit badge and registration forms. Stop spreading panic.", "platform": "x", "timestamp": "2026-02-27T15:30:00Z"},
    {"id": "post_104", "account_id": "acc_45", "text": "Fact check on the Scout posts flooding your timeline: (1) Girls NOT expelled — SA confirmed 200K+ stay. (2) No data going to Pentagon — just a liaison. (3) No YMCA/4-H plan — fabricated. (4) Audio 'leaks' are AI-generated. Source: @starsandstripes @nataliealund reporting.", "platform": "x", "timestamp": "2026-02-27T16:30:00Z", "source_url": "https://x.com/starsandstripes/status/2027470038111031629"},
    {"id": "post_105", "account_id": "acc_42", "text": "Trans parent of a Scout here. The actual policy change is bad enough — requiring biological sex on applications. We don't need people making up claims about '200K girls expelled' or 'Pentagon data grabs.' The real story is harmful enough without fabrication.", "platform": "reddit", "timestamp": "2026-02-27T16:00:00Z"},
    {"id": "post_106", "account_id": "acc_43", "text": "Scouting America Pentagon Deal: What ACTUALLY Changed vs. What's Being Fabricated Online — A Full Breakdown With Sources", "platform": "youtube", "timestamp": "2026-02-27T17:00:00Z", "media_url": "https://www.youtube.com/watch?v=gXDC5EdrUqM", "media_type": "video"},
    {"id": "post_107", "account_id": "acc_46", "text": "Military kid here. My mom called our troop leader in a panic because of the '200K girls expelled' posts. Troop leader had no idea what she was talking about because IT'S NOT HAPPENING. The disinfo around this story is insane.", "platform": "reddit", "timestamp": "2026-02-27T17:30:00Z"},
    {"id": "post_108", "account_id": "acc_47", "text": "Retired Colonel, 28 years of service, Eagle Scout 1984. The Pentagon has NO authority to 'take over' Scout troops or 'install military officers.' That's not how any of this works. The actual deal is about policy language. Please stop falling for rage bait.", "platform": "x", "timestamp": "2026-02-27T15:00:00Z"},
    {"id": "post_109", "account_id": "acc_41", "text": "Brian Allen's thread nails it: 'The Pentagon leveraging federal power to reshape a private youth organization's internal rules. That's not national security. That's culture war governance.' You can oppose the real policy without making stuff up.", "platform": "x", "timestamp": "2026-02-27T18:00:00Z", "source_url": "https://x.com/allenanalysis/status/2027391525995298950"},
    {"id": "post_110", "account_id": "acc_45", "text": "I've now tracked 30+ accounts pushing the '200K girls expelled' claim. ALL created in the last 48 hours. ALL using identical phrasing. ALL with under 25 followers. This is textbook coordinated inauthentic behavior. Thread with receipts:", "platform": "x", "timestamp": "2026-02-27T19:00:00Z"},
    {"id": "post_111", "account_id": "acc_44", "text": "Our council just sent official comms to all families: 'Scouting America has preserved its service to the more than 200,000 girls in our programs.' Direct quote. The '200K expelled' posts are fabricated. Please share the actual statement.", "platform": "x", "timestamp": "2026-02-27T18:30:00Z"},
]

# --- More echo/debunking posts ---
ECHO_EXTRA = [
    {"id": "post_112", "account_id": "acc_42", "text": "Did a deep dive on the Scout 'takeover' accounts. 30 accounts, all created Feb 26, all pushing word-for-word identical claims. This is not organic outrage, this is a coordinated disinfo campaign. The real policy change is bad enough without lies.", "platform": "reddit", "timestamp": "2026-02-27T20:30:00Z"},
    {"id": "post_113", "account_id": "acc_47", "text": "THREAD: As a retired military officer, let me explain why EVERY claim in the 'Pentagon Scout takeover' posts is structurally impossible. The DoD cannot install officers in civilian orgs. It cannot demand member data. It has no jurisdiction over YMCA or 4-H. This is fabricated.", "platform": "x", "timestamp": "2026-02-27T21:00:00Z"},
    {"id": "post_114", "account_id": "acc_46", "text": "The irony: people are so outraged by fake claims about Scouts that they're ignoring the REAL concerning thing — the Pentagon pressuring a youth org to change its trans policy under threat of funding withdrawal. That's the actual story worth discussing.", "platform": "reddit", "timestamp": "2026-02-27T21:30:00Z"},
    {"id": "post_115", "account_id": "acc_45", "text": "Final count: 34 accounts, all < 48 hours old, pushing identical 'Pentagon expelled 200K girls' narrative across X and Reddit. Zero of them link to any source. Zero have posting history before Feb 27. This is the clearest coordinated disinfo campaign I've documented this year.", "platform": "x", "timestamp": "2026-02-27T22:00:00Z"},
    {"id": "post_116", "account_id": "acc_43", "text": "UPDATE: How a Disinfo Campaign Hijacked the Scouting America Story — Tracking the Bot Network in Real Time", "platform": "youtube", "timestamp": "2026-02-27T22:00:00Z", "media_url": "https://www.youtube.com/shorts/q5Iw_8mulnc", "media_type": "video"},
]

# --- New user mentions ---
NEW_MENTIONS = [
    {"post_id": "post_81", "mentioned_account_id": "acc_01", "_note": "new bot cites original bot"},
    {"post_id": "post_83", "mentioned_account_id": "acc_05", "_note": "new bot amplifies original bot"},
    {"post_id": "post_84", "mentioned_account_id": "acc_02", "_note": "new bot amplifies original bot"},
    {"post_id": "post_85", "mentioned_account_id": "acc_11", "_note": "new bot points to YT bot"},
    {"post_id": "post_90", "mentioned_account_id": "acc_13", "_note": "wave 2 new bot cites bot"},
    {"post_id": "post_94", "mentioned_account_id": "acc_17", "_note": "wave 3 new bot cites bot"},
    {"post_id": "post_95", "mentioned_account_id": "acc_14", "_note": "wave 3 new bot cites bot"},
    {"post_id": "post_99", "mentioned_account_id": "acc_07", "_note": "wave 4 new bot cites bot"},
    {"post_id": "post_102", "mentioned_account_id": "acc_01", "_note": "organic veteran debunks main bot"},
    {"post_id": "post_104", "mentioned_account_id": "acc_01", "_note": "fact checker calls out main bot"},
    {"post_id": "post_104", "mentioned_account_id": "acc_03", "_note": "fact checker calls out bot"},
    {"post_id": "post_108", "mentioned_account_id": "acc_06", "_note": "colonel debunks bot claim"},
    {"post_id": "post_110", "mentioned_account_id": "acc_01", "_note": "fact checker tracks bots"},
    {"post_id": "post_110", "mentioned_account_id": "acc_31", "_note": "fact checker tracks new bots"},
    {"post_id": "post_113", "mentioned_account_id": "acc_04", "_note": "colonel debunks bot"},
    {"post_id": "post_115", "mentioned_account_id": "acc_01", "_note": "final count calls out main bot"},
    {"post_id": "post_115", "mentioned_account_id": "acc_31", "_note": "final count calls out new bots"},
]


def expand():
    with open(DATA_PATH) as f:
        data = json.load(f)

    # Add new accounts
    data["accounts"].extend(NEW_BOTS)
    data["accounts"].extend(NEW_ORGANIC)

    # Prepare new posts with defaults
    all_new_posts = []
    for post_list in [WAVE1_EXTRA, WAVE2_EXTRA, WAVE3_EXTRA, WAVE4_EXTRA, ORGANIC_EXTRA, ECHO_EXTRA]:
        for post in post_list:
            p = {
                "id": post["id"],
                "account_id": post["account_id"],
                "text": post["text"],
                "platform": post["platform"],
                "timestamp": post["timestamp"],
                "media_url": post.get("media_url", None),
                "media_type": post.get("media_type", None),
            }
            # Determine post type from which list it came from
            if post_list in [WAVE1_EXTRA, WAVE2_EXTRA, WAVE3_EXTRA, WAVE4_EXTRA]:
                p["post_type"] = "coordinated"
            elif post_list == ECHO_EXTRA:
                p["post_type"] = "echo"
            else:
                p["post_type"] = "organic"
            if "source_url" in post:
                p["source_url"] = post["source_url"]
            all_new_posts.append(p)

    data["posts"].extend(all_new_posts)

    # Add new mentions
    data["user_mentions"].extend(NEW_MENTIONS)

    with open(DATA_PATH, "w") as f:
        json.dump(data, f, indent=2)

    n_bots = len(NEW_BOTS)
    n_organic = len(NEW_ORGANIC)
    n_coord = len(WAVE1_EXTRA) + len(WAVE2_EXTRA) + len(WAVE3_EXTRA) + len(WAVE4_EXTRA)
    n_org_posts = len(ORGANIC_EXTRA)
    n_echo = len(ECHO_EXTRA)
    total_new = n_coord + n_org_posts + n_echo

    print(f"Added {n_bots} bot accounts + {n_organic} organic accounts = {n_bots + n_organic} new accounts")
    print(f"Added {n_coord} coordinated + {n_org_posts} organic + {n_echo} echo = {total_new} new posts")
    print(f"Added {len(NEW_MENTIONS)} new user mentions")
    print(f"\nTotal: {len(data['accounts'])} accounts, {len(data['posts'])} posts")


if __name__ == "__main__":
    expand()
