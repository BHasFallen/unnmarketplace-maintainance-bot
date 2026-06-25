"""
UNN Marketplace Auto-Cleaner
Runs every 2 days via Railway Cron Job.
- Deletes duplicate pending reposts of approved listings
- Cleans title/description text (strips [POSSIBLE DUPLICATE] tags, fixes typos)
- Fixes category miscategorizations
- Logs a full summary of changes
"""

import os
import re
import ssl
import logging
from difflib import SequenceMatcher
from urllib.parse import urlparse
import pg8000

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
)
log = logging.getLogger(__name__)

DATABASE_URL = os.environ["DATABASE_URL"]


def get_connection():
    """Parse DATABASE_URL and return a pg8000 connection."""
    url = urlparse(DATABASE_URL)
    return pg8000.connect(
        host=url.hostname,
        port=url.port or 5432,
        database=url.path.lstrip('/'),
        user=url.username,
        password=url.password,
        ssl_context=ssl.create_default_context(),
    )


def rows_as_dicts(cursor):
    """Convert pg8000 cursor rows (tuples) into list of dicts."""
    columns = [desc[0] for desc in cursor.description]
    return [dict(zip(columns, row)) for row in cursor.fetchall()]

# ---------------------------------------------------------------------------
# Text helpers
# ---------------------------------------------------------------------------

JUNK_PATTERNS = [
    r'\[POSSIBLE DUPLICATE[/\\]?REPOST\]\s*',
    r'\[POSSIBLE DUPLICATE\]\s*',
    r'\[REPOST\]\s*',
    r'\[DUPLICATE\]\s*',
]

def strip_junk(text: str) -> str:
    for pat in JUNK_PATTERNS:
        text = re.sub(pat, '', text, flags=re.IGNORECASE)
    stripped = text.strip()
    if stripped in {'.', '..', '...', '-', '--'}:
        return ''
    return stripped.strip()


TITLE_FIXES = [
    (r'\bLevovo\b',   'Lenovo'),
    (r'\bH@f\b',      'H&F'),
    (r'\bNfid\b',     'NFC'),
    (r'\b6by4\b',     '6x4'),
    (r'\b4by6ft\b',   '4x6'),
    (r'\b4by6\b',     '4x6'),
    (r'\bFt\b',       'ft'),
    (r'\bRom\b',      'ROM'),
    (r'\bRam\b',      'RAM'),
    (r'\bMifi\b',     'MiFi'),
    (r'\bMtn\b',      'MTN'),
    (r'\bGlo\b',      'GLO'),
    (r'\bHp\b',       'HP'),
    (r'\bLg\b',       'LG'),
    (r'\bDstv\b',     'DSTV'),
    (r'\bPs4\b',      'PS4'),
    (r'\bPs5\b',      'PS5'),
    (r'\bSsd\b',      'SSD'),
    (r'\bHdd\b',      'HDD'),
    (r'\bAc\b',       'AC'),
    (r'\bUnn\b',      'UNN'),
    (r'\bWifi\b',     'Wi-Fi'),
    (r'\bWi-fi\b',    'Wi-Fi'),
]

def clean_title(title: str) -> str:
    title = strip_junk(title)
    if not title:
        return title
    title = title.title()
    for pattern, replacement in TITLE_FIXES:
        title = re.sub(pattern, replacement, title)
    return title.strip()


def clean_description(desc: str) -> str:
    desc = strip_junk(desc)
    desc = re.sub(r'\s+', ' ', desc).strip()
    if desc in {'.', '..', '...', '-', '--', 'N/A', 'n/a'}:
        return ''
    if desc and not desc[0].isupper():
        desc = desc[0].upper() + desc[1:]
    return desc


# ---------------------------------------------------------------------------
# Category rules (priority order — most specific first)
# ---------------------------------------------------------------------------

CATEGORY_PRIORITY_RULES = [
    (['iphone', 'samsung galaxy', 'redmi', 'tecno', 'infinix', 'oppo',
      'tecno spark', 'tecno pova', 'samsung a', 'itel a'],
     ['iphone', 'samsung galaxy', 'redmi', 'tecno spark', 'infinix hot',
      'oppo a73', 'face id', 'true tone'],
     'Phones'),

    (['laptop', 'notebook', 'macbook', 'probook', 'elitebook', 'thinkpad',
      'dell latitude', 'hp 250', 'samsung laptop'],
     ['laptop', 'macbook', 'probook', 'elitebook', 'thinkpad', 'dell latitude'],
     'Laptops'),

    (['bike', 'motorcycle', 'scooter', 'haojue', 'kymstone', 'honda scooter'],
     ['bike', 'motorcycle', 'scooter'],
     'Vehicles'),

    (['earring', 'necklace', 'bangle', 'gold set braclet', 'jewelry', 'jewellery',
      'gold set', 'gold earring', 'complete set jewel',
      'jean', 'palazzo', 'sneaker', 'shoe',
      'chrome heart', 'cross chain', 'zodiac', 'besties necklace',
      'blue cuts lens', 'cat eye', 'butterfly medal'],
     ['earring', 'necklace', 'bangle', 'non-tarnishable'],
     'Clothing'),

    (['router', 'mifi', 'wi-fi router', 'airtel router', 'mtn router', 'glo router',
      'power bank', 'powerbank',
      'speaker', 'home cinema', 'sound system', 'jbl', 'zealot', 'alipu',
      'ps4', 'ps5', 'console',
      'camera', 'nikon', 'dslr',
      'clipper', 'wahl', 'philips clipper',
      'smartwatch', 'g-shock', 'wahl clipper',
      'keyboard', 'yamaha keyboard',
      'tv stand', 'tv console',
      'dstv',
      'influencer light', 'ring light',
      'laptop stand',
      'guitar', 'acoustic guitar',
      'radio', 'amplifier',
      'phone stand'],
     ['router', 'mifi', 'power bank', 'powerbank', 'speaker system',
      'home cinema', 'ps4', 'ps5', 'smartwatch', 'clipper', 'guitar',
      'ring light', 'influencer light'],
     'Electronics'),

    (['fridge', 'freezer', 'deep freezer', 'microwave',
      'air conditioner', ' ac ', 'haier ac', 'hisense ac',
      'ceiling fan', 'standing fan', 'ox fan',
      'generator', 'gen ', 'firman', 'sumec', 'skyrun gen',
      'gas cylinder', 'gas cooker', 'cooker', 'oven', 'gas burner', 'burner',
      'blender', 'pressing iron', 'electric iron', 'hot plate',
      'voltage stabilizer', 'stabilizer',
      'buta', 'skyrun fridge', 'skyrun', 'hisense fridge',
      'lg fridge', 'lg standing fridge',
      'mortar pestle', 'mortar and pestle',
      'dissection set',
      'iron wall rack', 'shoe rack',
      'frying pan',
      'flame', 'rechargeable clipper',
      'makeup brush',
      'jbl boombox',
      '500 gallon', 'gp tank',
      'gallon tank'],
     ['fridge', 'freezer', 'air conditioner', 'generator', 'gas cylinder',
      'voltage stabilizer', 'burner', 'blender', 'pressing iron', 'electric iron',
      'hot plate', 'microwave', 'gas cooker'],
     'Appliances'),

    (['foam', 'mattress', 'pillow', 'bucket', 'gallon',
      'plate', 'cup', 'pot', 'basket',
      'water pipe', 'hose', 'clothe basket', 'grinder',
      'iron container', 'orthopedic foam', 'orthopedic mattress',
      'student company bed', 'company foam'],
     ['foam', 'mattress', 'pillow', 'bucket', 'gallon', 'plate', 'cup',
      'orthopedic', 'grinder'],
     'Hostel Items'),

    (['bed', 'bedstand', 'bed frame', 'bed and bedstand',
      'wardrobe', 'cupboard', 'kitchen cupboard',
      'shelf', 'shelves',
      'table', 'chair', 'stool',
      'couch', 'sofa',
      'mirror', 'designer mirror', 'customized mirror',
      'curtain', 'curtains', 'window blind',
      'rug', 'carpet', 'centre rug',
      'drawer', 'bedside drawer',
      'portrait',
      'center table', 'centre table', 'dining table',
      'show glass',
      'wall hanger', 'clothe hanger',
      'glass center table',
      'clothes hanger'],
     ['wardrobe', 'cupboard', 'mirror', 'curtain', 'window blind',
      'center table', 'dining table', 'bedside drawer'],
     'Furniture'),
]


def fix_category(title: str, description: str, current_cat: str) -> str:
    title_lower = title.lower()
    desc_lower  = description.lower()
    for title_kws, desc_kws, cat in CATEGORY_PRIORITY_RULES:
        for kw in title_kws:
            if kw.lower() in title_lower:
                return cat
        for kw in desc_kws:
            if kw.lower() in desc_lower:
                return cat
    CAT_NORMALIZE = {'Accessories': 'Electronics', 'Services': 'Other'}
    return CAT_NORMALIZE.get(current_cat, current_cat)


# ---------------------------------------------------------------------------
# Deduplication helpers
# ---------------------------------------------------------------------------

def normalize_phone(phone: str) -> str:
    digits = re.sub(r'\D', '', phone or '')
    if digits.startswith('0') and len(digits) == 11:
        return digits
    if digits.startswith('234') and len(digits) == 13:
        return '0' + digits[3:]
    if len(digits) == 10:
        return '0' + digits
    return digits


def similarity(a: str, b: str) -> float:
    if not a or not b:
        return 0.0
    return SequenceMatcher(None, a.lower().strip(), b.lower().strip()).ratio()


def normalize_location(loc: str) -> str:
    return re.sub(r'\s+', ' ', (loc or '').lower().strip())


def is_true_duplicate(pending: dict, approved: dict) -> bool:
    pt = (pending['title'] or '').lower().strip()
    at = (approved['title'] or '').lower().strip()
    if pt != at:
        return False
    if str(pending['price']).strip() != str(approved['price']).strip():
        return False
    pl = normalize_location(pending['location'])
    al = normalize_location(approved['location'])
    if similarity(pl, al) < 0.70:
        return False
    pd = (pending['description'] or '').lower().strip()
    ad = (approved['description'] or '').lower().strip()
    desc_sim = similarity(pd, ad)
    pp = normalize_phone(pending.get('phone_number', ''))
    ap = normalize_phone(approved.get('phone_number', ''))
    phone_match = (pp == ap and len(pp) >= 8)
    return desc_sim >= 0.65 or phone_match


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    log.info("=== UNN Marketplace Auto-Cleaner starting ===")

    conn = get_connection()
    conn.autocommit = False
    cur = conn.cursor()

    # 1. Load all listings
    cur.execute("SELECT * FROM listings")
    all_rows = rows_as_dicts(cur)
    log.info(f"Loaded {len(all_rows)} listings from database")

    approved_rows = [r for r in all_rows if r['status'] in ('approved', 'sold')]
    pending_rows  = [r for r in all_rows if r['status'] == 'pending']
    log.info(f"  Approved/Sold: {len(approved_rows)}  |  Pending: {len(pending_rows)}")

    # 2. Deduplication — pending vs approved, then pending vs pending
    deleted_ids   = []
    kept_pending  = []

    for pr in pending_rows:
        is_dup = False
        # Check against approved
        for ar in approved_rows:
            if is_true_duplicate(pr, ar):
                is_dup = True
                log.info(
                    f"  DUP: pending {pr['id'][:8]} '{pr['title']}' "
                    f"@ {pr['price']} in {pr['location']} "
                    f"→ dup of approved {ar['id'][:8]}"
                )
                break
        # Check against already-kept pending
        if not is_dup:
            for kp in kept_pending:
                if is_true_duplicate(pr, kp):
                    is_dup = True
                    log.info(
                        f"  DUP: pending {pr['id'][:8]} '{pr['title']}' "
                        f"@ {pr['price']} in {pr['location']} "
                        f"→ dup of pending {kp['id'][:8]}"
                    )
                    break
        if is_dup:
            deleted_ids.append(pr['id'])
        else:
            kept_pending.append(pr)

    # 3. Delete duplicates
    if deleted_ids:
        # pg8000 doesn't support ANY with list — use IN with placeholders
        placeholders = ', '.join(['%s'] * len(deleted_ids))
        cur.execute(
            f"DELETE FROM listings WHERE id::text IN ({placeholders})",
            [str(i) for i in deleted_ids]
        )
        log.info(f"Deleted {len(deleted_ids)} duplicate listings")
    else:
        log.info("No duplicates found — nothing to delete")

    # 4. Text cleaning + category fixes on all surviving rows
    final_rows = approved_rows + kept_pending
    updates = []

    for row in final_rows:
        orig_title = row['title'] or ''
        orig_desc  = row['description'] or ''
        orig_cat   = row['category'] or ''

        new_title = clean_title(orig_title)
        new_desc  = clean_description(orig_desc)
        new_cat   = fix_category(new_title, new_desc, orig_cat)

        if new_title != orig_title or new_desc != orig_desc or new_cat != orig_cat:
            updates.append((new_title, new_desc, new_cat, row['id']))

    if updates:
        cur.executemany(
            "UPDATE listings SET title = %s, description = %s, category = %s WHERE id = %s",
            updates
        )
        log.info(f"Updated text/category on {len(updates)} listings")
    else:
        log.info("No text or category changes needed")

    conn.commit()
    cur.close()
    conn.close()

    log.info("=== Done ===")
    log.info(f"  Duplicates deleted : {len(deleted_ids)}")
    log.info(f"  Rows updated       : {len(updates)}")
    log.info(f"  Clean pending kept : {len(kept_pending)} (awaiting manual review)")


if __name__ == '__main__':
    main()
