# AW Client Report Portal — Deployment Notes

The portal is a FastAPI + SQLite app with HTML/CSS-rendered PDFs (WeasyPrint).
The only environment-specific friction is **WeasyPrint's native dependencies**
(Pango, Cairo, GDK-PixBuf). Use Docker on the server; install GTK locally on
Windows for dev.

---

## Environment variables

| Var | Required | Default | Purpose |
|---|---|---|---|
| `RAILWAY_DATABASE_PATH` | no | `./data/portal.db` | SQLite file location. Point at a mounted volume in prod. |
| `CANVA_API_KEY` | no | — | Activates `POST /api/reports/{id}/export-canva`. Absent → 501. |
| `CANVA_API_BASE` | no | `https://api.canva.com/rest/v1` | Override for staging/proxies. |
| `AW_DEV_SEED` | no | — | When `=1`, seeds the 6 demo households on startup if DB is empty. |
| `AW_ALLOW_DEV_SEED` | no | — | When `=1`, exposes `POST /api/dev/seed`. **Leave unset in prod.** |
| `PORT` | no | `8000` | Bound by the start command. |

---

## Railway

Railway runs the included **[Dockerfile](Dockerfile)** as-is. Steps:

1. **Mount a volume** at `/data` so SQLite survives redeploys. Set
   `RAILWAY_DATABASE_PATH=/data/portal.db` in the service vars (already the
   Dockerfile default).
2. Add `CANVA_API_KEY` if Canva export is wanted.
3. Push. The container's start command is
   `uvicorn app.main:app --host 0.0.0.0 --port $PORT`.
4. To seed initial demo data once: temporarily set `AW_ALLOW_DEV_SEED=1`, hit
   `POST /api/dev/seed`, then unset the flag and redeploy.

### Manual buildpack alternative (no Docker)

If you prefer Railway's Python buildpack, add these apt packages in
`nixpacks.toml` or via the service's "system dependencies" field:

```
libpango-1.0-0 libpangoft2-1.0-0 libpangocairo-1.0-0 libcairo2
libgdk-pixbuf-2.0-0 libffi8 libjpeg62-turbo shared-mime-info fonts-dejavu-core
```

Start command stays `uvicorn app.main:app --host 0.0.0.0 --port $PORT`.

---

## Local dev — macOS / Linux

```bash
pip install -r requirements.txt
# WeasyPrint deps:
#   macOS:  brew install pango libffi gdk-pixbuf
#   Debian: sudo apt-get install libpango-1.0-0 libpangoft2-1.0-0 libpangocairo-1.0-0 libcairo2 libgdk-pixbuf-2.0-0
python -m scripts.seed
python -m uvicorn app.main:app --reload
```

---

## Local dev — Windows

WeasyPrint on Windows needs the **GTK3 runtime**. Two options:

**A) Native install (recommended for fast iteration):**

1. Install MSYS2 from https://www.msys2.org and run, in the MSYS2 MinGW64
   shell:
   ```
   pacman -S mingw-w64-x86_64-pango mingw-w64-x86_64-cairo
   ```
2. Add `C:\msys64\mingw64\bin` to your **user** PATH and restart the terminal.
3. `python -m uvicorn app.main:app --reload --port 8765` (port 8000 is often
   in Windows' Hyper-V excluded range — pick anything else).

**B) Docker (matches production exactly):**

```powershell
docker build -t aw_portal .
docker run --rm -p 8000:8000 -v ${PWD}\data:/data aw_portal
```

If WeasyPrint can't load its libs, **the preview endpoint
(`GET /api/reports/{id}/preview?type=sacs|tcc`) still works** — it returns the
raw HTML and is the recommended path for iterating on the templates.

---

## Smoke checks (post-deploy)

```bash
curl https://<host>/api/clients                                       # list
curl -o sacs.pdf https://<host>/api/reports/<id>/pdf?type=sacs       # binary PDF
curl https://<host>/api/reports/<id>/preview?type=tcc                # raw HTML
```

A successful PDF response includes
`Content-Disposition: inline; filename="{Name}_{SACS|TCC}_{Quarter}.pdf"`.
