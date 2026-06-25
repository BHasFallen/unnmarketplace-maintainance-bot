# UNN Marketplace Auto-Cleaner — Railway Setup

A Python cron job that runs every 2 days to clean your Supabase marketplace database.

**What it does automatically:**
- Deletes duplicate `pending` reposts of already-approved listings
- Strips `[POSSIBLE DUPLICATE/REPOST]` tags from titles and descriptions
- Normalizes title casing and fixes brand name typos (HP, LG, MTN, etc.)
- Fixes category miscategorizations (Accessories → Electronics, etc.)
- Leaves clean pending listings alone (they stay pending for your manual review)

---

## 1. Push to GitHub

Create a new private GitHub repo and push this folder:

```bash
git init
git add .
git commit -m "Initial commit"
git remote add origin https://github.com/YOUR_USERNAME/marketplace-cleaner.git
git push -u origin main
```

---

## 2. Get your Supabase DATABASE_URL

1. Go to your **Supabase Dashboard** → Project Settings → Database
2. Scroll to **Connection string** → select **URI** tab
3. Copy the string — it looks like:
   ```
   postgresql://postgres:[YOUR-PASSWORD]@db.pmojbjbyxqesqxhieyao.supabase.co:5432/postgres
   ```
4. Replace `[YOUR-PASSWORD]` with your actual DB password

---

## 3. Deploy on Railway

1. Go to [railway.app](https://railway.app) → **New Project** → **Deploy from GitHub repo**
2. Select your `marketplace-cleaner` repo
3. Once deployed, click the service → **Settings** tab
4. Change **Service Type** to **Cron Job**
5. Set **Cron Schedule**: `0 2 */2 * *` *(runs at 2am every 2 days)*
6. Set **Start Command**: `python cleaner.py`

---

## 4. Add Environment Variable

In Railway → your service → **Variables** tab, add:

| Key | Value |
|-----|-------|
| `DATABASE_URL` | `postgresql://postgres:PASSWORD@db.pmojbjbyxqesqxhieyao.supabase.co:5432/postgres` |

---

## 5. Test it manually

In Railway → your service → **Deployments** → click **Trigger Run** to test it immediately.

Check the logs — you should see output like:
```
2026-06-25 [INFO] === UNN Marketplace Auto-Cleaner starting ===
2026-06-25 [INFO] Loaded 1004 listings from database
2026-06-25 [INFO] Approved/Sold: 1004  |  Pending: 0
2026-06-25 [INFO] No duplicates found — nothing to delete
2026-06-25 [INFO] No text or category changes needed
2026-06-25 [INFO] === Done ===
```

---

## Cron Schedule Reference

| Schedule | Meaning |
|----------|---------|
| `0 2 */2 * *` | Every 2 days at 2am ✅ (recommended) |
| `0 2 * * *`   | Every day at 2am |
| `0 2 */3 * *` | Every 3 days at 2am |

---

## Notes

- The script only modifies `title`, `description`, and `category` — all other columns are untouched
- It never deletes `approved` or `sold` listings — only confirmed duplicate `pending` reposts
- Clean `pending` listings (unique ones) are left as `pending` for your manual review
- Completely free on Railway's Hobby plan (cron jobs use minimal resources)
