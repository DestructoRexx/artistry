import os
import json
import shutil
import glob
import hashlib
from datetime import datetime, timezone
from fastapi import FastAPI, Request, HTTPException, UploadFile, File, Form, Response
from fastapi.responses import HTMLResponse, RedirectResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from typing import Optional
from themes import PRESET_THEMES, FRAME_STYLES, ANIMATION_SNIPPETS, sanitize_custom_html, sanitize_custom_css

app = FastAPI()
templates = Jinja2Templates(directory="templates")

os.makedirs("static/uploads", exist_ok=True)
os.makedirs("tenants", exist_ok=True)
app.mount("/static", StaticFiles(directory="static"), name="static")

USERS_FILE = "users.json"
ARTWORKS_FILE = "artworks.json"
COMMENTS_FILE = "comments.json"

ALLOWED_IMAGE_EXTS = {".jpg", ".jpeg", ".png", ".webp", ".gif"}
ALLOWED_BG_EXTS = {".jpg", ".jpeg", ".png", ".webp", ".gif", ".mp4", ".webm"}
MAX_BG_VIDEO_BYTES = 4 * 1024 * 1024  # 4 MB strict limit for crisp, lightweight MP4/WebM loops

def get_safe_ext(filename: str) -> str:
    ext = os.path.splitext(filename or "")[1].lower()
    return ext if ext in ALLOWED_IMAGE_EXTS else ".jpg"

def get_safe_bg_ext(filename: str) -> str:
    ext = os.path.splitext(filename or "")[1].lower()
    return ext if ext in ALLOWED_BG_EXTS else ".jpg"

def normalize_social_url(platform: str, raw_val: str) -> str:
    val = (raw_val or "").strip()
    if not val:
        return ""
    if val.startswith("http://") or val.startswith("https://"):
        return val
    handle = val.lstrip("@")
    bases = {
        "instagram": f"https://instagram.com/{handle}",
        "twitter": f"https://x.com/{handle}",
        "tiktok": f"https://tiktok.com/@{handle}",
        "youtube": f"https://youtube.com/@{handle}",
        "artstation": f"https://artstation.com/{handle}",
        "website": f"https://{val}"
    }
    return bases.get(platform, val)

def is_safe_media_url(url: str, allow_video: bool = False) -> bool:
    u = (url or "").strip()
    if not (u.startswith("http://") or u.startswith("https://") or u.startswith("/static/")):
        return False
    clean_path = u.split("?")[0].lower()
    disallowed = (".avi", ".mkv", ".mov", ".m4v") if allow_video else (".mp4", ".webm", ".mov", ".avi", ".mkv", ".m4v")
    if clean_path.endswith(disallowed):
        return False
    return True

# ----------------------------
# LOCAL JSON STORAGE HELPERS
# ----------------------------

def get_users():
    if os.path.exists(USERS_FILE):
        with open(USERS_FILE, "r") as f:
            try:
                return json.load(f)
            except Exception:
                return []
    return []

def save_users(users):
    with open(USERS_FILE, "w") as f:
        json.dump(users, f, indent=2)

def get_artworks():
    if os.path.exists(ARTWORKS_FILE):
        with open(ARTWORKS_FILE, "r") as f:
            try:
                return json.load(f)
            except Exception:
                return []
    return []

def save_artworks(artworks):
    with open(ARTWORKS_FILE, "w") as f:
        json.dump(artworks, f, indent=2)

def get_comments():
    if os.path.exists(COMMENTS_FILE):
        with open(COMMENTS_FILE, "r") as f:
            try:
                return json.load(f)
            except Exception:
                return []
    return []

def save_comments(comments):
    with open(COMMENTS_FILE, "w") as f:
        json.dump(comments, f, indent=2)

def _format_relative_time(iso_str: str) -> str:
    try:
        dt = datetime.fromisoformat(iso_str)
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        diff = datetime.now(timezone.utc) - dt
        secs = max(0, int(diff.total_seconds()))
        if secs < 60:
            return "Just now"
        if secs < 3600:
            return f"{secs // 60}m"
        if secs < 86400:
            return f"{secs // 3600}h"
        if secs < 604800:
            return f"{secs // 86400}d"
        return dt.strftime("%b %d")
    except Exception:
        return "Recently"

def _resolve_commenter_identity(user_dict: dict) -> dict:
    email = (user_dict.get("email") or "").lower()
    role = user_dict.get("role", "collector")
    tenant_slug = user_dict.get("tenant_slug") or ""
    if role == "artist" and tenant_slug:
        cfg = get_tenant_config(tenant_slug)
        return {
            "display_name": cfg.get("brand_name") or email.split("@")[0],
            "avatar_url": cfg.get("avatar_url", "/static/uploads/default_avatar.jpg"),
            "role": "artist",
            "tenant_slug": tenant_slug
        }
    return {
        "display_name": email.split("@")[0] if email else "Collector",
        "avatar_url": "",
        "role": "collector",
        "tenant_slug": ""
    }

def build_product_comment_threads(product_id: int, artist_slug: str, current_user: Optional[dict]) -> tuple[list, int]:
    raw = [c for c in get_comments() if c.get("product_id") == product_id]
    viewer_email = (current_user or {}).get("email", "").lower()
    viewer_is_post_artist = bool(
        current_user
        and current_user.get("role") == "artist"
        and current_user.get("tenant_slug") == artist_slug
    )

    enriched_map = {}
    for c in raw:
        author_email = (c.get("author_email") or "").lower()
        can_delete = bool(viewer_email and (author_email == viewer_email or viewer_is_post_artist))
        item = {
            **c,
            "time_ago": _format_relative_time(c.get("created_at", "")),
            "is_post_author": bool(c.get("author_role") == "artist" and c.get("author_slug") == artist_slug),
            "can_delete": can_delete,
            "replies": []
        }
        enriched_map[c["id"]] = item

    roots = []
    for c in raw:
        item = enriched_map[c["id"]]
        parent_id = c.get("parent_id")
        if parent_id and parent_id in enriched_map:
            enriched_map[parent_id]["replies"].append(item)
        else:
            roots.append(item)

    return roots, len(raw)

def hash_password(password: str) -> str:
    return hashlib.sha256(password.encode()).hexdigest()

def get_tenant_config(tenant_slug: str):
    file_path = f"tenants/{tenant_slug}.json"
    default_socials = {
        "instagram": "",
        "twitter": "",
        "tiktok": "",
        "youtube": "",
        "artstation": "",
        "discord": "",
        "website": ""
    }
    default_theme_settings = {
        "preset_id": "gallery_white",
        "show_cover": True,
        "header_style": "banner",
        "grid_cols": 5,
        "frame_size": "standard",
        "art_frame_style": "none",
        "avatar_frame_style": "none",
        "custom_avatar_overlay_url": "",
        "custom_art_overlay_url": "",
        "bg_image_url": "",
        "bg_style": "cover",
        "animation": "none",
        "ambient_gif_url": "",
        "custom_mode": False,
        "custom_css": "",
        "custom_html": ""
    }
    if os.path.exists(file_path):
        with open(file_path, "r") as f:
            config = json.load(f)
            if "avatar_url" not in config:
                config["avatar_url"] = "/static/uploads/default_avatar.jpg"
            if "cover_url" not in config:
                config["cover_url"] = "/static/uploads/default_cover.jpg"
            if "socials" not in config:
                config["socials"] = default_socials
            else:
                for k, v in default_socials.items():
                    config["socials"].setdefault(k, v)
            if "theme_settings" not in config:
                config["theme_settings"] = default_theme_settings
            else:
                for k, v in default_theme_settings.items():
                    config["theme_settings"].setdefault(k, v)
            if "saved_themes" not in config:
                config["saved_themes"] = []
            return config

    default_config = {
        "tenant_id": tenant_slug,
        "brand_name": tenant_slug.replace("_", " ").title(),
        "bio": "Visual artist and creative director crafting original contemporary works.",
        "avatar_url": "/static/uploads/default_avatar.jpg",
        "cover_url": "/static/uploads/default_cover.jpg",
        "socials": default_socials,
        "theme_settings": default_theme_settings,
        "saved_themes": [],
        "hero_title": f"STUDIO: {tenant_slug.upper()}",
        "hero_subtitle": "Curated gallery space powered by Artistry."
    }
    with open(file_path, "w") as f:
        json.dump(default_config, f, indent=2)
    return default_config

def get_current_user(request: Request):
    user_cookie = request.cookies.get("artistry_user")
    if user_cookie:
        try:
            return json.loads(user_cookie)
        except Exception:
            return None
    return None

def get_artist_info_by_slug(tenant_slug: str):
    if not tenant_slug:
        return {"name": "Artistry Creator", "slug": "artist_studio"}
    config = get_tenant_config(tenant_slug)
    return {
        "name": config.get("brand_name", "Artistry Creator"),
        "slug": tenant_slug
    }

def enrich_artwork(art: dict):
    tenant_slug = art.get("tenant_slug") or "artist_studio"
    artist_info = get_artist_info_by_slug(tenant_slug)
    img_url = art.get("image_url", f"/static/uploads/product_{art['id']}.jpg")
    masonry_heights = ["h-52", "h-80", "h-64", "h-96", "h-60", "h-72"]
    seed = (art["id"] * 7 + len(art.get("name", ""))) % len(masonry_heights)
    return {
        "id": art["id"],
        "name": art.get("name", "Untitled Artwork"),
        "artist_name": artist_info["name"],
        "artist_slug": artist_info["slug"],
        "list_price": float(art.get("list_price", 0.0)),
        "image_url": img_url,
        "is_gif": img_url.lower().endswith(".gif"),
        "masonry_height": masonry_heights[seed]
    }

# ----------------------------
# PUBLIC DISCOVERY ROUTES
# ----------------------------

@app.get("/", response_class=HTMLResponse)
async def home_page(request: Request):
    current_user = get_current_user(request)
    raw_artworks = [a for a in get_artworks() if a.get("active", True)]
    raw_artworks.sort(key=lambda x: x["id"], reverse=True)
    products = [enrich_artwork(a) for a in raw_artworks[:10]]
    return templates.TemplateResponse(request, "home.html", {"products": products, "user": current_user})

@app.get("/gallery", response_class=HTMLResponse)
async def global_gallery(request: Request, search: Optional[str] = None):
    current_user = get_current_user(request)
    raw_artworks = [a for a in get_artworks() if a.get("active", True)]
    if search:
        q = search.lower()
        raw_artworks = [a for a in raw_artworks if q in a.get("name", "").lower()]
    raw_artworks.sort(key=lambda x: x["id"], reverse=True)
    products = [enrich_artwork(a) for a in raw_artworks[:40]]
    return templates.TemplateResponse(request, "gallery.html", {"products": products, "search": search or "", "user": current_user})

@app.get("/artists", response_class=HTMLResponse)
async def artist_directory(request: Request):
    current_user = get_current_user(request)
    artists = []
    try:
        for file_path in glob.glob("tenants/*.json"):
            with open(file_path, "r") as f:
                config = json.load(f)
                artists.append({
                    "slug": config.get("tenant_id"),
                    "name": config.get("brand_name"),
                    "bio": config.get("bio", "Independent Visual Artist"),
                    "avatar_url": config.get("avatar_url", "/static/uploads/default_avatar.jpg")
                })
    except Exception as e:
        print(f"Error loading artists: {e}")

    return templates.TemplateResponse(request, "artists.html", {"artists": artists, "user": current_user})

@app.get("/site/{tenant_slug}", response_class=HTMLResponse)
async def render_artist_public_profile(request: Request, tenant_slug: str):
    current_user = get_current_user(request)
    config = get_tenant_config(tenant_slug)
    ts = config["theme_settings"]
    preset_id = ts.get("preset_id", "gallery_white")
    preset = PRESET_THEMES.get(preset_id, PRESET_THEMES["gallery_white"])
    anim_css = ANIMATION_SNIPPETS.get(ts.get("animation", "none"), "")
    art_frame_css = FRAME_STYLES.get(ts.get("art_frame_style", "none"), FRAME_STYLES["none"])["art_css"]
    avatar_frame_css = FRAME_STYLES.get(ts.get("avatar_frame_style", "none"), FRAME_STYLES["none"])["avatar_css"]

    raw_artworks = [
        a for a in get_artworks()
        if a.get("active", True) and a.get("tenant_slug") == tenant_slug
    ]
    raw_artworks.sort(key=lambda x: x["id"], reverse=True)
    products = [enrich_artwork(a) for a in raw_artworks[:30]]

    is_pinterest = (preset_id == "pinterest_mode") or (ts.get("frame_size") == "pinterest")
    bg_url_clean = (ts.get("bg_image_url") or "").split("?")[0].lower()
    is_bg_video = bg_url_clean.endswith((".mp4", ".webm"))

    return templates.TemplateResponse(request, "studio_public.html", {
        "config": config,
        "products": products,
        "user": current_user,
        "preset": preset,
        "anim_css": anim_css,
        "art_frame_css": art_frame_css,
        "avatar_frame_css": avatar_frame_css,
        "is_pinterest": is_pinterest,
        "is_bg_video": is_bg_video
    })

# ----------------------------
# SECURE AUTHENTICATION ROUTES
# ----------------------------

@app.get("/login", response_class=HTMLResponse)
async def login_page(request: Request):
    return templates.TemplateResponse(request, "login.html", {"error": None})

@app.post("/api/auth/login")
async def process_login(request: Request, email: str = Form(...), password: str = Form(...)):
    users = get_users()
    hashed_pwd = hash_password(password)

    matched_user = None
    for u in users:
        if u["email"].lower() == email.lower() and u["password"] == hashed_pwd:
            matched_user = u
            break

    if not matched_user:
        return templates.TemplateResponse(request, "login.html", {"error": "Invalid email or password. Please try again."})

    user_data = {
        "email": matched_user["email"],
        "role": matched_user["role"],
        "tenant_slug": matched_user.get("tenant_slug", "artist_studio")
    }

    redirect_url = f"/studio/{user_data['tenant_slug']}" if user_data["role"] == "artist" else "/gallery"
    resp = RedirectResponse(url=redirect_url, status_code=303)
    resp.set_cookie(key="artistry_user", value=json.dumps(user_data), path="/")
    return resp

@app.get("/signup", response_class=HTMLResponse)
async def signup_page(request: Request):
    return templates.TemplateResponse(request, "signup.html", {"error": None})

@app.post("/api/auth/signup")
async def process_signup(
    request: Request,
    email: str = Form(...),
    password: str = Form(...),
    role: str = Form(...),
    studio_name: Optional[str] = Form(None)
):
    users = get_users()

    for u in users:
        if u["email"].lower() == email.lower():
            return templates.TemplateResponse(request, "signup.html", {"error": "That email is already taken."})

    tenant_slug = "artist_studio"

    if role == "artist":
        if not studio_name:
            studio_name = email.split("@")[0]
        tenant_slug = studio_name.lower().replace(" ", "_")

        for u in users:
            if u.get("tenant_slug") == tenant_slug:
                return templates.TemplateResponse(request, "signup.html", {"error": "That studio name is already taken. Please choose another."})

        get_tenant_config(tenant_slug)

    new_user = {
        "email": email.lower(),
        "password": hash_password(password),
        "role": role,
        "tenant_slug": tenant_slug
    }

    users.append(new_user)
    save_users(users)

    cookie_data = {
        "email": new_user["email"],
        "role": new_user["role"],
        "tenant_slug": tenant_slug
    }

    redirect_url = f"/studio/{tenant_slug}" if role == "artist" else "/gallery"
    resp = RedirectResponse(url=redirect_url, status_code=303)
    resp.set_cookie(key="artistry_user", value=json.dumps(cookie_data), path="/")
    return resp

@app.get("/logout")
async def logout(response: Response):
    resp = RedirectResponse(url="/", status_code=303)
    resp.delete_cookie("artistry_user", path="/")
    return resp

# ----------------------------
# ARTIST STUDIO & DASHBOARD
# ----------------------------

@app.get("/studio/{tenant_slug}", response_class=HTMLResponse)
async def artist_studio(request: Request, tenant_slug: str, tab: Optional[str] = "profile", error: Optional[str] = None):
    current_user = get_current_user(request)
    if not current_user or current_user.get("role") != "artist":
        return RedirectResponse(url="/login", status_code=303)

    if current_user.get("tenant_slug") != tenant_slug:
        return RedirectResponse(url=f"/studio/{current_user.get('tenant_slug')}", status_code=303)

    config = get_tenant_config(tenant_slug)
    raw_artworks = [
        a for a in get_artworks()
        if a.get("active", True) and a.get("tenant_slug") == tenant_slug
    ]
    raw_artworks.sort(key=lambda x: x["id"], reverse=True)
    products = [enrich_artwork(a) for a in raw_artworks]

    return templates.TemplateResponse(request, "studio.html", {
        "config": config,
        "products": products,
        "active_tab": tab,
        "error": error,
        "user": current_user,
        "presets": PRESET_THEMES,
        "frame_styles": FRAME_STYLES
    })

# ----------------------------
# SETTINGS HUB ROUTES
# ----------------------------

@app.get("/studio/settings/account", response_class=HTMLResponse)
async def account_settings_page(request: Request):
    current_user = get_current_user(request)
    if not current_user:
        return RedirectResponse(url="/login", status_code=303)
    return templates.TemplateResponse(request, "account_settings.html", {"user": current_user})

@app.post("/api/account/change-password")
async def change_password(request: Request, current_password: str = Form(...), new_password: str = Form(...)):
    current_user = get_current_user(request)
    if not current_user:
        return RedirectResponse(url="/login", status_code=303)

    users = get_users()
    email = current_user.get("email")
    hashed_current = hash_password(current_password)

    user_found = False
    for u in users:
        if u["email"].lower() == email.lower():
            if u["password"] != hashed_current:
                return RedirectResponse(url="/studio/settings/account?error=incorrect_current_password", status_code=303)
            u["password"] = hash_password(new_password)
            user_found = True
            break

    if user_found:
        save_users(users)
        return RedirectResponse(url="/studio/settings/account?msg=password_updated", status_code=303)

    return RedirectResponse(url="/studio/settings/account?error=user_not_found", status_code=303)

@app.post("/api/account/update-email")
async def update_email(request: Request, new_email: str = Form(...), password: str = Form(...)):
    current_user = get_current_user(request)
    if not current_user:
        return RedirectResponse(url="/login", status_code=303)

    email = current_user.get("email")
    users = get_users()
    hashed_pwd = hash_password(password)

    user_target = None
    for u in users:
        if u["email"].lower() == email.lower():
            if u["password"] != hashed_pwd:
                return RedirectResponse(url="/studio/settings/account?error=incorrect_password", status_code=303)
            user_target = u
            break

    if not user_target:
        return RedirectResponse(url="/studio/settings/account?error=user_not_found", status_code=303)

    for u in users:
        if u["email"].lower() == new_email.lower() and u["email"].lower() != email.lower():
            return RedirectResponse(url="/studio/settings/account?error=email_taken", status_code=303)

    user_target["email"] = new_email.lower()
    save_users(users)

    current_user["email"] = new_email.lower()
    resp = RedirectResponse(url="/studio/settings/account?msg=email_updated", status_code=303)
    resp.set_cookie(key="artistry_user", value=json.dumps(current_user), path="/")
    return resp

@app.get("/api/account/export-data")
async def export_data(request: Request):
    current_user = get_current_user(request)
    if not current_user:
        return RedirectResponse(url="/login", status_code=303)

    tenant_slug = current_user.get("tenant_slug")
    config = get_tenant_config(tenant_slug)

    products = [
        {
            "id": a["id"],
            "name": a.get("name", "Untitled Artwork"),
            "price": float(a.get("list_price", 0.0)),
            "active": a.get("active", True)
        }
        for a in get_artworks()
        if a.get("tenant_slug") == tenant_slug
    ]

    export_payload = {
        "export_metadata": {
            "platform": "Artistry Gallery",
            "ecosystem": "ZisandaHub",
            "exported_at_user": current_user.get("email")
        },
        "user_account": {
            "email": current_user.get("email"),
            "role": current_user.get("role"),
            "tenant_slug": tenant_slug
        },
        "studio_config": config,
        "artwork_listings": products
    }

    filename = f"artistry_gallery_{tenant_slug}_backup.json"
    return JSONResponse(
        content=export_payload,
        headers={"Content-Disposition": f"attachment; filename={filename}"}
    )

@app.post("/api/account/delete")
async def delete_account(request: Request, password: str = Form(...)):
    current_user = get_current_user(request)
    if not current_user:
        return RedirectResponse(url="/login", status_code=303)

    email = current_user.get("email")
    tenant_slug = current_user.get("tenant_slug")

    users = get_users()
    hashed_pwd = hash_password(password)
    user_found = False
    for u in users:
        if u["email"].lower() == email.lower() and u["password"] == hashed_pwd:
            user_found = True
            break

    if not user_found:
        return RedirectResponse(url="/studio/settings/account?error=invalid_password", status_code=303)

    users = [u for u in users if u["email"].lower() != email.lower()]
    save_users(users)

    artworks = get_artworks()
    remaining_artworks = []
    for a in artworks:
        if a.get("tenant_slug") == tenant_slug:
            img_path = a.get("image_url", "").lstrip("/")
            if img_path and os.path.exists(img_path):
                os.remove(img_path)
        else:
            remaining_artworks.append(a)
    save_artworks(remaining_artworks)

    tenant_file = f"tenants/{tenant_slug}.json"
    if os.path.exists(tenant_file):
        os.remove(tenant_file)

    response = RedirectResponse(url="/?msg=account_deleted", status_code=303)
    response.delete_cookie("artistry_user", path="/")
    return response

# ----------------------------
# ARTIST STUDIO MANAGEMENT API
# ----------------------------

async def _build_theme_settings_from_form(
    config: dict,
    tenant_slug: str,
    preset_id: str,
    show_cover: Optional[str],
    header_style: str,
    grid_cols: int,
    frame_size: str,
    art_frame_style: str,
    avatar_frame_style: str,
    custom_avatar_overlay_url: str,
    custom_art_overlay_url: str,
    avatar_overlay_file: Optional[UploadFile],
    art_overlay_file: Optional[UploadFile],
    bg_image_url: str,
    bg_file: Optional[UploadFile],
    bg_style: str,
    animation: str,
    ambient_gif_url: str,
    custom_mode: Optional[str],
    custom_css: str,
    custom_html: str
) -> dict:
    existing_ts = config.get("theme_settings", {})

    avatar_overlay = custom_avatar_overlay_url.strip() if is_safe_media_url(custom_avatar_overlay_url) else ""
    if avatar_overlay_file and avatar_overlay_file.filename:
        ext = get_safe_ext(avatar_overlay_file.filename)
        fname = f"frame_avatar_{tenant_slug}_{os.urandom(4).hex()}{ext}"
        fpath = f"static/uploads/{fname}"
        with open(fpath, "wb+") as f:
            shutil.copyfileobj(avatar_overlay_file.file, f)
        avatar_overlay = f"/{fpath}"

    art_overlay = custom_art_overlay_url.strip() if is_safe_media_url(custom_art_overlay_url) else ""
    if art_overlay_file and art_overlay_file.filename:
        ext = get_safe_ext(art_overlay_file.filename)
        fname = f"frame_art_{tenant_slug}_{os.urandom(4).hex()}{ext}"
        fpath = f"static/uploads/{fname}"
        with open(fpath, "wb+") as f:
            shutil.copyfileobj(art_overlay_file.file, f)
        art_overlay = f"/{fpath}"

    bg_url = bg_image_url.strip() if is_safe_media_url(bg_image_url, allow_video=True) else ""
    if bg_file and bg_file.filename:
        ext = get_safe_bg_ext(bg_file.filename)
        file_bytes = await bg_file.read()
        if ext in (".mp4", ".webm") and len(file_bytes) > MAX_BG_VIDEO_BYTES:
            raise ValueError("bg_video_too_large")
        fname = f"bg_{tenant_slug}_{os.urandom(4).hex()}{ext}"
        fpath = f"static/uploads/{fname}"
        with open(fpath, "wb+") as f:
            f.write(file_bytes)
        bg_url = f"/{fpath}"
    elif not bg_image_url.strip() and existing_ts.get("bg_image_url") and existing_ts.get("bg_image_url").startswith("/static/uploads/bg_"):
        bg_url = ""

    safe_gif_url = ambient_gif_url.strip() if is_safe_media_url(ambient_gif_url) else ""

    return {
        "preset_id": preset_id if preset_id in PRESET_THEMES else "gallery_white",
        "show_cover": show_cover == "true",
        "header_style": header_style if header_style in ("banner", "centered", "minimal") else "banner",
        "grid_cols": grid_cols if grid_cols in (3, 4, 5) else 5,
        "frame_size": frame_size if frame_size in ("compact", "standard", "tall", "wide", "pinterest") else "standard",
        "art_frame_style": art_frame_style if art_frame_style in FRAME_STYLES else "none",
        "avatar_frame_style": avatar_frame_style if avatar_frame_style in FRAME_STYLES else "none",
        "custom_avatar_overlay_url": avatar_overlay,
        "custom_art_overlay_url": art_overlay,
        "bg_image_url": bg_url,
        "bg_style": bg_style if bg_style in ("cover", "repeat", "contain") else "cover",
        "animation": animation if animation in ANIMATION_SNIPPETS else "none",
        "ambient_gif_url": safe_gif_url,
        "custom_mode": custom_mode == "true",
        "custom_css": sanitize_custom_css(custom_css),
        "custom_html": sanitize_custom_html(custom_html)
    }

@app.post("/api/artist/update-profile")
async def update_artist_profile(
    tenant_slug: str = Form(...),
    brand_name: str = Form(...),
    bio: str = Form(...),
    instagram: str = Form(""),
    twitter: str = Form(""),
    tiktok: str = Form(""),
    youtube: str = Form(""),
    artstation: str = Form(""),
    discord: str = Form(""),
    website: str = Form(""),
    avatar: Optional[UploadFile] = File(None),
    cover: Optional[UploadFile] = File(None)
):
    config = get_tenant_config(tenant_slug)
    config["brand_name"] = brand_name
    config["bio"] = bio
    config["socials"] = {
        "instagram": normalize_social_url("instagram", instagram),
        "twitter": normalize_social_url("twitter", twitter),
        "tiktok": normalize_social_url("tiktok", tiktok),
        "youtube": normalize_social_url("youtube", youtube),
        "artstation": normalize_social_url("artstation", artstation),
        "discord": discord.strip(),
        "website": normalize_social_url("website", website)
    }

    if avatar and avatar.filename:
        ext = get_safe_ext(avatar.filename)
        avatar_filename = f"avatar_{tenant_slug}_{os.urandom(4).hex()}{ext}"
        avatar_path = f"static/uploads/{avatar_filename}"
        with open(avatar_path, "wb+") as f:
            shutil.copyfileobj(avatar.file, f)
        config["avatar_url"] = f"/{avatar_path}"

    if cover and cover.filename:
        ext = get_safe_ext(cover.filename)
        cover_filename = f"cover_{tenant_slug}_{os.urandom(4).hex()}{ext}"
        cover_path = f"static/uploads/{cover_filename}"
        with open(cover_path, "wb+") as f:
            shutil.copyfileobj(cover.file, f)
        config["cover_url"] = f"/{cover_path}"

    with open(f"tenants/{tenant_slug}.json", "w") as f:
        json.dump(config, f, indent=2)

    return RedirectResponse(url=f"/studio/{tenant_slug}?tab=profile", status_code=303)

@app.post("/api/artist/update-theme")
async def update_artist_theme(
    tenant_slug: str = Form(...),
    preset_id: str = Form("gallery_white"),
    show_cover: Optional[str] = Form(None),
    header_style: str = Form("banner"),
    grid_cols: int = Form(5),
    frame_size: str = Form("standard"),
    art_frame_style: str = Form("none"),
    avatar_frame_style: str = Form("none"),
    custom_avatar_overlay_url: str = Form(""),
    custom_art_overlay_url: str = Form(""),
    avatar_overlay_file: Optional[UploadFile] = File(None),
    art_overlay_file: Optional[UploadFile] = File(None),
    bg_image_url: str = Form(""),
    bg_file: Optional[UploadFile] = File(None),
    bg_style: str = Form("cover"),
    animation: str = Form("none"),
    ambient_gif_url: str = Form(""),
    custom_mode: Optional[str] = Form(None),
    custom_css: str = Form(""),
    custom_html: str = Form("")
):
    config = get_tenant_config(tenant_slug)
    try:
        config["theme_settings"] = await _build_theme_settings_from_form(
            config=config,
            tenant_slug=tenant_slug,
            preset_id=preset_id,
            show_cover=show_cover,
            header_style=header_style,
            grid_cols=grid_cols,
            frame_size=frame_size,
            art_frame_style=art_frame_style,
            avatar_frame_style=avatar_frame_style,
            custom_avatar_overlay_url=custom_avatar_overlay_url,
            custom_art_overlay_url=custom_art_overlay_url,
            avatar_overlay_file=avatar_overlay_file,
            art_overlay_file=art_overlay_file,
            bg_image_url=bg_image_url,
            bg_file=bg_file,
            bg_style=bg_style,
            animation=animation,
            ambient_gif_url=ambient_gif_url,
            custom_mode=custom_mode,
            custom_css=custom_css,
            custom_html=custom_html
        )
    except ValueError as err:
        return RedirectResponse(url=f"/studio/{tenant_slug}?tab=theme&error={err}", status_code=303)

    with open(f"tenants/{tenant_slug}.json", "w") as f:
        json.dump(config, f, indent=2)

    return RedirectResponse(url=f"/studio/{tenant_slug}?tab=theme", status_code=303)

@app.post("/api/artist/theme/save-named")
async def save_named_theme(
    tenant_slug: str = Form(...),
    theme_name: str = Form(...),
    preset_id: str = Form("gallery_white"),
    show_cover: Optional[str] = Form(None),
    header_style: str = Form("banner"),
    grid_cols: int = Form(5),
    frame_size: str = Form("standard"),
    art_frame_style: str = Form("none"),
    avatar_frame_style: str = Form("none"),
    custom_avatar_overlay_url: str = Form(""),
    custom_art_overlay_url: str = Form(""),
    avatar_overlay_file: Optional[UploadFile] = File(None),
    art_overlay_file: Optional[UploadFile] = File(None),
    bg_image_url: str = Form(""),
    bg_file: Optional[UploadFile] = File(None),
    bg_style: str = Form("cover"),
    animation: str = Form("none"),
    ambient_gif_url: str = Form(""),
    custom_mode: Optional[str] = Form(None),
    custom_css: str = Form(""),
    custom_html: str = Form("")
):
    config = get_tenant_config(tenant_slug)
    clean_name = (theme_name or "").strip()[:60] or "Untitled Custom Theme"
    saved = config.setdefault("saved_themes", [])

    try:
        built_ts = await _build_theme_settings_from_form(
            config=config,
            tenant_slug=tenant_slug,
            preset_id=preset_id,
            show_cover=show_cover,
            header_style=header_style,
            grid_cols=grid_cols,
            frame_size=frame_size,
            art_frame_style=art_frame_style,
            avatar_frame_style=avatar_frame_style,
            custom_avatar_overlay_url=custom_avatar_overlay_url,
            custom_art_overlay_url=custom_art_overlay_url,
            avatar_overlay_file=avatar_overlay_file,
            art_overlay_file=art_overlay_file,
            bg_image_url=bg_image_url,
            bg_file=bg_file,
            bg_style=bg_style,
            animation=animation,
            ambient_gif_url=ambient_gif_url,
            custom_mode=custom_mode,
            custom_css=custom_css,
            custom_html=custom_html
        )
    except ValueError as err:
        return RedirectResponse(url=f"/studio/{tenant_slug}?tab=theme&error={err}", status_code=303)

    theme_snapshot = {"name": clean_name, **built_ts}

    replaced = False
    for idx, item in enumerate(saved):
        if item.get("name", "").lower() == clean_name.lower():
            saved[idx] = theme_snapshot
            replaced = True
            break
    if not replaced:
        saved.append(theme_snapshot)

    config["theme_settings"] = built_ts

    with open(f"tenants/{tenant_slug}.json", "w") as f:
        json.dump(config, f, indent=2)

    return RedirectResponse(url=f"/studio/{tenant_slug}?tab=theme", status_code=303)

@app.post("/api/artist/theme/load-named")
async def load_named_theme(
    tenant_slug: str = Form(...),
    theme_index: int = Form(...)
):
    config = get_tenant_config(tenant_slug)
    saved = config.get("saved_themes", [])
    if 0 <= theme_index < len(saved):
        chosen = saved[theme_index]
        config["theme_settings"] = {k: v for k, v in chosen.items() if k != "name"}
        with open(f"tenants/{tenant_slug}.json", "w") as f:
            json.dump(config, f, indent=2)
    return RedirectResponse(url=f"/studio/{tenant_slug}?tab=theme", status_code=303)

@app.post("/api/artist/theme/delete-named")
async def delete_named_theme(
    tenant_slug: str = Form(...),
    theme_index: int = Form(...)
):
    config = get_tenant_config(tenant_slug)
    saved = config.get("saved_themes", [])
    if 0 <= theme_index < len(saved):
        saved.pop(theme_index)
        config["saved_themes"] = saved
        with open(f"tenants/{tenant_slug}.json", "w") as f:
            json.dump(config, f, indent=2)
    return RedirectResponse(url=f"/studio/{tenant_slug}?tab=theme", status_code=303)

@app.post("/api/artist/artwork/create")
async def create_artwork(
    tenant_slug: str = Form(...),
    name: str = Form(...),
    price: float = Form(...),
    file: UploadFile = File(...)
):
    try:
        artworks = get_artworks()
        next_id = max([a["id"] for a in artworks], default=0) + 1
        ext = get_safe_ext(file.filename)

        file_location = f"static/uploads/product_{next_id}{ext}"
        with open(file_location, "wb+") as file_object:
            shutil.copyfileobj(file.file, file_object)

        artworks.append({
            "id": next_id,
            "tenant_slug": tenant_slug,
            "name": name,
            "list_price": float(price),
            "image_url": f"/{file_location}",
            "active": True
        })
        save_artworks(artworks)

        return RedirectResponse(url=f"/studio/{tenant_slug}?tab=artworks", status_code=303)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/artist/artwork/edit/{product_id}")
async def edit_artwork(
    product_id: int,
    tenant_slug: str = Form(...),
    name: str = Form(...),
    price: float = Form(...),
    file: Optional[UploadFile] = File(None)
):
    try:
        artworks = get_artworks()
        target = None
        for a in artworks:
            if a["id"] == product_id and a.get("tenant_slug") == tenant_slug:
                a["name"] = name
                a["list_price"] = float(price)
                target = a
                break

        if not target:
            raise HTTPException(status_code=404, detail="Artwork not found")

        if file and file.filename:
            ext = get_safe_ext(file.filename)
            file_location = f"static/uploads/product_{product_id}{ext}"
            with open(file_location, "wb+") as file_object:
                shutil.copyfileobj(file.file, file_object)
            target["image_url"] = f"/{file_location}"

        save_artworks(artworks)
        return RedirectResponse(url=f"/studio/{tenant_slug}?tab=artworks", status_code=303)
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/artist/artwork/delete/{product_id}")
async def delete_artwork(product_id: int, tenant_slug: str = Form(...)):
    try:
        artworks = get_artworks()
        for a in artworks:
            if a["id"] == product_id and a.get("tenant_slug") == tenant_slug:
                a["active"] = False
                break
        save_artworks(artworks)
        return RedirectResponse(url=f"/studio/{tenant_slug}?tab=artworks", status_code=303)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

# ----------------------------
# CORE PRODUCT DETAIL & COMMENTS
# ----------------------------

@app.get("/product/{product_id}", response_class=HTMLResponse)
async def product_detail(request: Request, product_id: int):
    current_user = get_current_user(request)
    product = None

    for a in get_artworks():
        if a["id"] == product_id and a.get("active", True):
            product = enrich_artwork(a)
            break

    if not product:
        raise HTTPException(status_code=404, detail="Product not found")

    comment_threads, total_comments = build_product_comment_threads(
        product_id=product_id,
        artist_slug=product["artist_slug"],
        current_user=current_user
    )

    return templates.TemplateResponse(request, "product.html", {
        "product": product,
        "user": current_user,
        "comment_threads": comment_threads,
        "total_comments": total_comments
    })

@app.post("/api/product/{product_id}/comments")
async def create_product_comment(
    request: Request,
    product_id: int,
    body: str = Form(...),
    parent_id: Optional[int] = Form(None),
    reply_to_name: str = Form("")
):
    current_user = get_current_user(request)
    if not current_user:
        return RedirectResponse(url="/login", status_code=303)

    artwork = next((a for a in get_artworks() if a["id"] == product_id and a.get("active", True)), None)
    if not artwork:
        raise HTTPException(status_code=404, detail="Artwork not found")

    clean_body = (body or "").strip()[:1000]
    if not clean_body:
        return RedirectResponse(url=f"/product/{product_id}#comments", status_code=303)

    comments = get_comments()
    valid_parent_id = None
    if parent_id:
        parent_comment = next(
            (c for c in comments if c["id"] == parent_id and c.get("product_id") == product_id),
            None
        )
        if parent_comment:
            valid_parent_id = parent_comment.get("parent_id") or parent_comment["id"]

    identity = _resolve_commenter_identity(current_user)
    next_id = max([c["id"] for c in comments], default=0) + 1

    comments.append({
        "id": next_id,
        "product_id": product_id,
        "parent_id": valid_parent_id,
        "reply_to_name": (reply_to_name or "").strip()[:60] if valid_parent_id else "",
        "author_email": current_user["email"].lower(),
        "author_name": identity["display_name"],
        "author_avatar": identity["avatar_url"],
        "author_role": identity["role"],
        "author_slug": identity["tenant_slug"],
        "body": clean_body,
        "created_at": datetime.now(timezone.utc).isoformat()
    })
    save_comments(comments)

    return RedirectResponse(url=f"/product/{product_id}#comment-{next_id}", status_code=303)

@app.post("/api/product/{product_id}/comments/{comment_id}/delete")
async def delete_product_comment(request: Request, product_id: int, comment_id: int):
    current_user = get_current_user(request)
    if not current_user:
        return RedirectResponse(url="/login", status_code=303)

    artwork = next((a for a in get_artworks() if a["id"] == product_id), None)
    if not artwork:
        raise HTTPException(status_code=404, detail="Artwork not found")

    comments = get_comments()
    target = next((c for c in comments if c["id"] == comment_id and c.get("product_id") == product_id), None)
    if not target:
        return RedirectResponse(url=f"/product/{product_id}#comments", status_code=303)

    viewer_email = current_user.get("email", "").lower()
    is_comment_author = (target.get("author_email") or "").lower() == viewer_email
    is_artwork_artist = (
        current_user.get("role") == "artist"
        and current_user.get("tenant_slug") == artwork.get("tenant_slug")
    )

    if not (is_comment_author or is_artwork_artist):
        raise HTTPException(status_code=403, detail="Not authorized to delete this comment")

    remaining = [
        c for c in comments
        if not (c.get("product_id") == product_id and (c["id"] == comment_id or c.get("parent_id") == comment_id))
    ]
    save_comments(remaining)

    return RedirectResponse(url=f"/product/{product_id}#comments", status_code=303)