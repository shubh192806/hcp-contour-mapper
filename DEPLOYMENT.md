# Deploying so your mam can open it from anywhere

This gets you a real public URL, using free hosting you control. Nothing here
requires sharing any password or token with anyone — every step below is a
click in your own dashboard, using your own GitHub login.

Three parts: push the code to your GitHub, deploy the backend (Render),
deploy the frontend (Vercel), point them at each other.

## 1. Push to your GitHub

If you don't already have a repo for this project, create an empty one on
github.com first (no README/license — just an empty repo), then:

```bash
cd hcp-mapper
git init
git add .
git commit -m "HCP Contour Mapper"
git branch -M main
git remote add origin https://github.com/<your-username>/<your-repo>.git
git push -u origin main
```

If you already have a repo and this is just an update:

```bash
cd hcp-mapper
git add .
git commit -m "N-tier color scale, PDF reports, deployment config"
git push
```

## 2. Deploy the backend (Render, free tier)

1. Go to [render.com](https://render.com), sign in with GitHub.
2. **New +** → **Blueprint**. Pick your repo. Render will find `render.yaml`
   at the repo root automatically and pre-fill everything (root dir
   `backend`, build/start commands) — you shouldn't need to type anything.
3. Click **Apply**. First deploy takes a few minutes (installing scipy/
   matplotlib/reportlab isn't instant).
4. Once it's live, copy the URL Render gives you — looks like
   `https://hcp-contour-mapper-backend.onrender.com`. You'll need it in step 3.
5. Sanity check: open `<that-url>/api/health` in a browser. You should see
   `{"status":"ok",...}`.

**Free tier caveat, worth knowing before you rely on it for a demo:** Render's
free web services spin down after 15 minutes of no traffic, and spin back up
(taking ~30-60 seconds) on the next request. If your mam opens the link after
it's been idle, the first load will feel slow — that's normal, not broken.
Also, the SQLite database file lives on Render's disk, which is **not
persistent on the free tier** — a redeploy or restart can reset your data.
Uploaded slab photos live on the same disk and carry the identical risk —
a redeploy can wipe them too. Fine for demoing the tool; download your PDF
reports and CSV exports for anything you need to keep.
Fine for demoing the tool; download your PDF reports and CSV exports for
anything you need to keep.

## 3. Deploy the frontend (Vercel, free tier)

1. Go to [vercel.com](https://vercel.com), sign in with GitHub.
2. **Add New** → **Project**. Pick the same repo.
3. Vercel will ask for a **Root Directory** — set it to `frontend`. It should
   auto-detect the framework as Vite; leave build command / output directory
   as the defaults.
4. Before deploying, add an environment variable:
   **Name:** `VITE_API_BASE_URL`
   **Value:** the Render URL from step 2 (no trailing slash), e.g.
   `https://hcp-contour-mapper-backend.onrender.com`
5. Click **Deploy**. A couple minutes later you get a URL like
   `https://hcp-contour-mapper.vercel.app` — that's the one to send your mam.

## 4. If you change the code later

Every `git push` to `main` auto-redeploys both services — Render and Vercel
both watch the repo. No repeat setup needed; just push.

## 5. If something's not connecting

- Frontend loads but every action fails → check `VITE_API_BASE_URL` in
  Vercel's project settings has no typo and no trailing slash, then
  redeploy (Vercel → Deployments → ⋯ → Redeploy) so the env var actually
  gets baked into the build.
- Backend URL shows an error page instead of `{"status":"ok"}` → check
  Render's **Logs** tab for the actual Python traceback.
- Contour map or PDF report requests fail specifically → these are the
  heaviest endpoints (scipy interpolation, matplotlib rendering); if the
  free-tier instance just woke up from sleep, retry once after a few seconds.
