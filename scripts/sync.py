#!/usr/bin/env python3
"""
Reel Stats — sincroniza tus Reels de Instagram en tu computadora.

Un solo comando:
  1. Descarga tus Reels públicos con sus métricas y transcripción (Apify, actor apify/instagram-reel-scraper).
  2. Clasifica cada transcripción con Claude (temática, formato, gancho, tono). Cachea el resultado.
  3. Guarda un snapshot de métricas para ver la evolución con el tiempo.
  4. Genera el panel: data/panel.html (ábrelo con doble clic, sin servidor).

Uso:
  python3 scripts/sync.py --limit 5            # prueba barata
  python3 scripts/sync.py                      # historial completo
  python3 scripts/sync.py --no-transcript      # solo métricas (más barato, sin temática)
  python3 scripts/sync.py --no-classify        # transcribe pero no gasta Claude
  python3 scripts/sync.py --dry-run            # no llama a ninguna API; muestra qué haría

Credenciales: archivo .env en la carpeta raíz del skill (ver .env.example). Nunca se imprimen.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DATA = ROOT / "data"
RAW_DIR = DATA / "raw"
THEMES_CACHE = DATA / "themes.json"          # shortCode -> clasificación de Claude
REELS_PATH = DATA / "reels.json"             # métricas + temática de todos tus reels
HISTORY_PATH = DATA / "history.jsonl"        # un renglón por sincronización y reel
PANEL_PATH = DATA / "panel.html"

ACTOR_ID = "apify/instagram-reel-scraper"
CLAUDE_MODEL = "claude-haiku-5-5"            # clasificar es tarea simple; modelo barato
GANCHOS = ["pregunta", "contraste", "número", "dolor", "historia", "mito", "otro"]

PANEL_TEMPLATE = Path(__file__).resolve().parent / "panel_template.html"


# --------------------------------------------------------------------------- utilidades

def load_env() -> None:
    """Lee .env sin depender de python-dotenv (menos instalaciones para la persona)."""
    env_path = ROOT / ".env"
    if not env_path.exists():
        return
    for line in env_path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        os.environ.setdefault(key.strip(), value.strip().strip('"').strip("'"))


def read_json(path: Path, default):
    if not path.exists():
        return default
    return json.loads(path.read_text(encoding="utf-8"))


def write_json(path: Path, data) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")


def fail(msg: str) -> None:
    print(f"ERROR: {msg}", file=sys.stderr)
    sys.exit(1)


# --------------------------------------------------------------------------- normalización

def first_number(*values) -> int:
    """Primer valor numérico no nulo. Instagram cambió varios contadores de vistas."""
    for v in values:
        if isinstance(v, (int, float)):
            return int(v)
    return 0


def normalize(item: dict, snapshot_at: str) -> dict | None:
    """Convierte un item crudo del actor a un registro simple. None si el item es un error."""
    if item.get("error") or not item.get("shortCode"):
        return None
    views = first_number(item.get("videoPlayCount"), item.get("igPlayCount"), item.get("videoViewCount"))
    likes = first_number(item.get("likesCount"))
    comments = first_number(item.get("commentsCount"))
    shares = first_number(item.get("sharesCount"), item.get("reshareCount"))
    engagement = round((likes + comments) / views, 4) if views > 0 else 0.0
    return {
        "shortCode": item["shortCode"],
        "ownerUsername": item.get("ownerUsername") or "",
        "url": item.get("url") or f"https://www.instagram.com/reel/{item['shortCode']}/",
        "timestamp": item.get("timestamp"),
        "duration": item.get("videoDuration"),
        "caption": (item.get("caption") or "")[:600],
        "transcript": item.get("transcript") or "",
        "views": views,
        "likes": likes,
        "comments": comments,
        "shares": shares,
        "engagement": engagement,          # (likes + comentarios) / vistas
        "snapshot_at": snapshot_at,
    }


# --------------------------------------------------------------------------- Apify

def fetch_items(token: str, username: str, limit: int, transcript: bool) -> list[dict]:
    from apify_client import ApifyClient  # import tardío: --dry-run no lo necesita

    run_input = {
        "username": [username],
        "resultsLimit": limit,
        "includeTranscript": transcript,
        "includeSharesCount": False,       # solo planes de pago en Instagram; desactivado por defecto
        "skipPinnedPosts": False,
    }
    from decimal import Decimal

    # Tope de gasto por corrida: APIFY_MAX_USD en .env (por defecto 5 USD).
    max_usd = Decimal(os.getenv("APIFY_MAX_USD", "5"))
    client = ApifyClient(token)
    print(f"  Apify: pidiendo hasta {limit} reels de @{username} (transcripción: {'sí' if transcript else 'no'}, tope {max_usd} USD)")
    run = client.actor(ACTOR_ID).call(run_input=run_input, max_total_charge_usd=max_usd)
    if not run:
        fail("Apify no devolvió una ejecución. Revisa tu token, tus créditos y que la cuenta sea pública.")
    dataset_id = run.get("defaultDatasetId")
    if not dataset_id:
        fail("Apify no devolvió dataset. Revisa tu token y que la cuenta sea pública.")
    items = list(client.dataset(dataset_id).iterate_items())
    RAW_DIR.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    write_json(RAW_DIR / f"{stamp}.json", items)   # respaldo crudo, por si cambia el formato
    return items


# --------------------------------------------------------------------------- Claude

PROMPT = """Clasifica este Reel de Instagram según su transcripción y su descripción.
Responde SOLO con un objeto JSON válido, sin texto extra, con estas claves:
- "tema": 2 a 4 palabras que digan de qué habla.
- "formato": uno de: "talking head", "tutorial", "historia personal", "lista", "reacción", "otro".
- "gancho": uno de: {gancho_opts}. Es cómo abre el video en los primeros segundos.
- "tono": una palabra (ej. "directo", "reflexivo", "divertido", "motivacional").

Transcripción:
{transcript}

Descripción:
{caption}
"""


def classify(anthropic_key: str, reel: dict) -> dict:
    import anthropic  # import tardío

    client = anthropic.Anthropic(api_key=anthropic_key)
    prompt = PROMPT.format(
        gancho_opts=", ".join(GANCHOS),
        transcript=reel["transcript"][:4000] or "(sin transcripción)",
        caption=reel["caption"] or "(sin descripción)",
    )
    msg = client.messages.create(
        model=CLAUDE_MODEL,
        max_tokens=200,
        messages=[{"role": "user", "content": prompt}],
    )
    text = msg.content[0].text.strip()
    start, end = text.find("{"), text.rfind("}")
    parsed = json.loads(text[start : end + 1])
    if parsed.get("gancho") not in GANCHOS:
        parsed["gancho"] = "otro"
    return parsed


# --------------------------------------------------------------------------- panel

def build_panel(reels: list[dict]) -> None:
    if not PANEL_TEMPLATE.exists():
        fail(f"Falta {PANEL_TEMPLATE.name} junto a sync.py. Reinstala el skill.")
    payload = json.dumps(reels, ensure_ascii=False).replace("</", "<\\/")
    html = PANEL_TEMPLATE.read_text(encoding="utf-8").replace("/*__REELS__*/[]", payload)
    PANEL_PATH.parent.mkdir(parents=True, exist_ok=True)
    PANEL_PATH.write_text(html, encoding="utf-8")


# --------------------------------------------------------------------------- main

def main() -> None:
    parser = argparse.ArgumentParser(description="Sincroniza tus Reels de Instagram")
    parser.add_argument("--limit", type=int, default=50, help="Máximo de reels a traer (prueba: 5)")
    parser.add_argument("--no-transcript", action="store_true", help="No pedir transcripción (más barato)")
    parser.add_argument("--no-classify", action="store_true", help="No clasificar con Claude")
    parser.add_argument("--dry-run", action="store_true", help="Muestra el plan sin llamar a ninguna API")
    args = parser.parse_args()

    load_env()
    username = os.getenv("IG_USERNAME", "").lstrip("@").strip()
    apify_token = os.getenv("APIFY_TOKEN", "").strip()
    anthropic_key = os.getenv("ANTHROPIC_API_KEY", "").strip()

    if not username:
        fail("Falta IG_USERNAME en .env")
    if not apify_token:
        fail("Falta APIFY_TOKEN en .env")
    use_transcript = not args.no_transcript
    use_classify = not args.no_classify and use_transcript
    if use_classify and not anthropic_key:
        fail("Falta ANTHROPIC_API_KEY en .env (o usa --no-classify)")

    print(f"Reel Stats · @{username} · límite {args.limit}")
    print(f"  transcripción Apify: {'sí' if use_transcript else 'no'} · clasificar con Claude: {'sí' if use_classify else 'no'}")
    if args.dry_run:
        print("  --dry-run: no se llamó a ninguna API. Quita --dry-run para ejecutar (gasta créditos).")
        return

    snapshot_at = datetime.now(timezone.utc).isoformat(timespec="seconds")
    items = fetch_items(apify_token, username, args.limit, use_transcript)
    fresh = [r for r in (normalize(i, snapshot_at) for i in items) if r]
    print(f"  Apify: {len(items)} items, {len(fresh)} válidos")

    themes = read_json(THEMES_CACHE, {})
    for reel in fresh:
        if use_classify and reel["shortCode"] not in themes and reel["transcript"]:
            try:
                themes[reel["shortCode"]] = classify(anthropic_key, reel)
                print(f"  Claude: {reel['shortCode']} clasificado")
            except Exception as exc:  # no tumbar todo por un reel
                print(f"  Claude: {reel['shortCode']} falló ({type(exc).__name__}); se reintenta la próxima vez")
        reel["classification"] = themes.get(reel["shortCode"], {})
    write_json(THEMES_CACHE, themes)

    # Snapshot de evolución: una línea por reel y por sincronización.
    DATA.mkdir(parents=True, exist_ok=True)
    with HISTORY_PATH.open("a", encoding="utf-8") as fh:
        for r in fresh:
            fh.write(json.dumps({k: r[k] for k in ("shortCode", "snapshot_at", "views", "likes", "comments", "shares")},
                                ensure_ascii=False) + "\n")

    write_json(REELS_PATH, fresh)
    build_panel(fresh)
    print(f"\nListo. {len(fresh)} reels.")
    print(f"Panel: {PANEL_PATH}  (ábrelo con doble clic)")


if __name__ == "__main__":
    main()
