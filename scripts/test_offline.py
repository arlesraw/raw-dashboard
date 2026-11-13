#!/usr/bin/env python3
"""
Pruebas sin conexión: no llaman a Apify ni a Claude y no gastan créditos.
Uso: python3 scripts/test_offline.py
Los datos de ejemplo son FALSOS, solo sirven para verificar el código.
"""
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import sync  # noqa: E402

FAKE_ITEMS = [
    {   # reel normal con transcripción
        "shortCode": "FAKE001", "url": "https://www.instagram.com/reel/FAKE001/",
        "timestamp": "2026-10-01T10:00:00.000Z", "videoDuration": 28.4,
        "caption": "ejemplo", "transcript": "texto de ejemplo",
        "videoPlayCount": 1000, "likesCount": 50, "commentsCount": 10,
    },
    {   # vistas en campo alterno y sin transcripción
        "shortCode": "FAKE002", "timestamp": "2026-10-03T10:00:00.000Z",
        "igPlayCount": 400, "likesCount": 20, "commentsCount": 0,
    },
    {   # error del actor: debe descartarse
        "shortCode": "FAKE003", "error": "not_found", "errorDescription": "x",
    },
    {   # sin vistas: engagement debe ser 0, no división entre cero
        "shortCode": "FAKE004", "likesCount": 3, "commentsCount": 1,
    },
]

failures = []


def check(name, cond):
    print(("OK   " if cond else "FAIL ") + name)
    if not cond:
        failures.append(name)


# 1. normalize
r1 = sync.normalize(FAKE_ITEMS[0], "2026-11-01T00:00:00+00:00")
check("normaliza vistas desde videoPlayCount", r1["views"] == 1000)
check("engagement = (likes+comentarios)/vistas", r1["engagement"] == 0.06)
check("conserva transcripción", r1["transcript"] == "texto de ejemplo")

r2 = sync.normalize(FAKE_ITEMS[1], "2026-11-01T00:00:00+00:00")
check("usa igPlayCount si falta videoPlayCount", r2["views"] == 400)
check("sin transcripción deja cadena vacía", r2["transcript"] == "")

check("descarta items con error", sync.normalize(FAKE_ITEMS[2], "x") is None)

r4 = sync.normalize(FAKE_ITEMS[3], "x")
check("sin vistas no divide entre cero", r4["engagement"] == 0.0)
check("URL se construye si falta", r4["url"].endswith("/reel/FAKE004/"))

# 2. el panel se genera y contiene los datos
sync.PANEL_PATH = Path(sync.DATA) / "_test_panel.html"
sync.build_panel([r1, r2, r4])
html = sync.PANEL_PATH.read_text(encoding="utf-8")
check("panel tiene el marcador reemplazado", "/*__REELS__*/[]" not in html)
check("panel incluye el shortCode de prueba", "FAKE001" in html)
check("panel no deja '</' sin escapar dentro del JSON", "</script></body>" not in html.split("const REELS")[1][:200000].split("];")[0])
sync.PANEL_PATH.unlink()

# 3. cache de temas: no vuelve a clasificar lo que ya existe
cache = {"FAKE001": {"tema": "x", "formato": "y", "gancho": "pregunta", "tono": "z"}}
called = []


def fake_classify(_key, reel):
    called.append(reel["shortCode"])
    return {"tema": "t", "formato": "f", "gancho": "inventado", "tono": "o"}


sync.classify = fake_classify
for r in [r1, r2]:
    if r["shortCode"] not in cache and r["transcript"]:
        cache[r["shortCode"]] = sync.classify("k", r)
check("no reclasifica un reel ya cacheado", "FAKE001" not in called)
check("sin transcripción no gasta Claude", "FAKE002" not in called)

# 4. gancho fuera de catálogo se corrige a 'otro' (dentro de classify real)
parsed = {"gancho": "inventado"}
if parsed.get("gancho") not in sync.GANCHOS:
    parsed["gancho"] = "otro"
check("gancho inválido se normaliza a 'otro'", parsed["gancho"] == "otro")

print()
if failures:
    print(f"{len(failures)} prueba(s) fallaron: {failures}")
    sys.exit(1)
print("Todas las pruebas pasaron.")
