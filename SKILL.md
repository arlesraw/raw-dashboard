---
name: raw-dashboard
description: >-
  Mide tus Reels de Instagram en tu computadora: descarga métricas y transcripciones con Apify, clasifica
  temática y gancho con Claude, guarda la evolución y genera un panel HTML que se abre con doble clic.
  Úsalo cuando digas "medir mis reels", "analizar mis reels", "qué reels funcionan", "sincronizar mis
  métricas" o "armar mi panel de reels".
---

# Reel Stats

**Qué hace:** te muestra qué Reels funcionan, por tema, formato y gancho, con sus métricas. Todo se queda
en tu computadora (carpeta `data/`). No hay servidor ni base de datos.

**Qué NO hace:** no decide qué publicar. Te muestra patrones; tú decides qué probar.

**Qué cuesta:** Apify cobra por ejecución y la transcripción tiene costo por minuto de audio. Claude cobra
por clasificación. El script tiene un tope de gasto por corrida (`APIFY_MAX_USD`, 5 USD por defecto).

---

## Reglas para ti, Claude

- **Antes de cualquier comando que gaste créditos** (`sync.py` sin `--dry-run`), pide confirmación
  explícita y di cuánto costará aproximadamente. Un `--limit 5` es la prueba recomendada.
- **Nunca pidas, muestres ni guardes** tokens o claves en el chat. Viven solo en `.env`.
- Si el usuario pega una clave, pídele que la rote y que la pegue en `.env`.
- No cambies `CLAUDE_MODEL` ni `ACTOR_ID` sin avisar: afectan costo y resultados.

---

## Requisitos de quien instala el skill

- Python 3.10 o superior (`python3 --version`).
- Una cuenta de Instagram **pública**.
- Un token de Apify (Settings → Integrations → Personal API tokens) con créditos.
- Una API key de Anthropic con crédito (console.anthropic.com).

Sin estos cuatro, el skill solo puede explicar pasos; no puede medir nada.

---

## Paso 1: Instala las dependencias (una vez)

```bash
python3 -m pip install apify-client anthropic
```

**Listo cuando:** el comando termina sin errores.

---

## Paso 2: Crea tu archivo de credenciales

Copia `.env.example` como `.env` en la carpeta del skill y rellena:

```
APIFY_TOKEN=...
ANTHROPIC_API_KEY=...
IG_USERNAME=tu_usuario_sin_arroba
APIFY_MAX_USD=5
```

**Listo cuando:** `.env` existe con las cuatro variables con valor. Nunca lo subas a GitHub.

---

## Paso 3: Verifica el código sin gastar nada

```bash
python3 scripts/test_offline.py
python3 scripts/sync.py --dry-run
```

La primera prueba usa datos falsos y no llama a ninguna API. La segunda muestra el plan sin ejecutar nada.

**Listo cuando:** la primera termina con "Todas las pruebas pasaron" y la segunda no muestra errores.

---

## Paso 4: Prueba con 5 reels (gasta créditos, pide confirmación)

```bash
python3 scripts/sync.py --limit 5
```

Hace cuatro cosas: descarga los reels, transcribe, clasifica con Claude, y genera el panel.

**Listo cuando:** `data/panel.html` existe y al abrirlo ves tus 5 reels con su tema y su gancho.

Si falla, revisa "Problemas frecuentes" antes de volver a intentar.

---

## Paso 5: Historial completo (gasta más, pide confirmación)

```bash
python3 scripts/sync.py
```

Antes de correrlo, dile al usuario cuántos reels tiene y el costo estimado.

Opciones útiles:
- `--no-transcript`: solo métricas, sin transcripción ni temática. Mucho más barato.
- `--no-classify`: transcribe pero no gasta en Claude.

**Listo cuando:** el número de reels del panel coincide con los públicos.

---

## Paso 6: Abre el panel

Abre `data/panel.html` con doble clic. Tiene el mismo estilo oscuro con acento azul, y muestra:
- **Dashboard:** cinco KPIs (vistas, publicados, vistas por reel, engagement, likes + comentarios) con su variación contra el periodo anterior.
- **Vistas acumuladas por publicación:** curva de vistas acumuladas por fecha de publicación.
- **Destacados:** los 5 reels con más vistas.
- **Publicaciones (14 semanas):** mapa de calor de cuántos reels publicaste por día.
- **Mejores videos:** ranking por vistas, comentarios, likes o engagement.
- **Desglose:** tabla de reels ordenable y buscable.
- **Temáticas y Ganchos:** promedios de vistas y engagement por categoría.

Filtro de periodo: 30 días, 90 días o todo el historial.

Limitación: el scraper público no trae guardados ni compartidos, así que el panel no los muestra.

**Engagement** = (likes + comentarios) / vistas.

---

## Problemas frecuentes

- **"Falta APIFY_TOKEN en .env":** el archivo `.env` no existe o la variable está vacía.
- **Apify no devuelve reels:** confirma que la cuenta es pública y que `IG_USERNAME` no lleva arroba.
- **"no devolvió una ejecución":** revisa créditos de Apify o sube `APIFY_MAX_USD` si la corrida se cortó por tope.
- **Reels sin clasificar:** el reel no tenía transcripción, o Claude falló. Se reintenta en la siguiente corrida.
- **El actor cambió de formato:** revisa su pestaña Output en Apify y ajusta `normalize()` en `scripts/sync.py`.

---

## Qué hay en la carpeta

- `scripts/sync.py`: descarga, clasifica y genera el panel.
- `scripts/panel_template.html`: plantilla del panel (un solo archivo, sin servidor).
- `scripts/test_offline.py`: pruebas sin conexión.
- `data/`: resultados locales (ignorado por git).
- `.env.example`: plantilla de credenciales.
