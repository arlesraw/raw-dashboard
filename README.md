# raw-dashboard

Skill de Claude Code para medir tus Reels de Instagram: descarga métricas y transcripciones con Apify, clasifica temática y gancho con Claude, y genera un panel HTML que se abre con doble clic. Todo se queda en tu computadora.

## Instalar

```bash
git clone https://github.com/darioarles04-cmd/raw-dashboard.git ~/.claude/skills/raw-dashboard
python3 -m pip install apify-client anthropic
```

Abre una sesión nueva de Claude Code y pídele: "quiero medir mis reels".

## Qué necesitas

- Python 3.10 o superior
- Una cuenta de Instagram pública
- Un token de Apify con créditos
- Una API key de Anthropic con crédito

Copia `.env.example` como `.env` y rellénalo con tus claves. Nunca subas `.env` a GitHub.

## Costos

Apify cobra por ejecución y por minuto de audio transcrito; Claude cobra por clasificación. El script tiene un tope de gasto por corrida (`APIFY_MAX_USD`, 5 USD por defecto). Empieza siempre con `--limit 5`.

## Verificar sin gastar

```bash
python3 scripts/test_offline.py
python3 scripts/sync.py --dry-run
```

Más detalle de cada paso en [SKILL.md](SKILL.md).
