# Contributing

Thanks for helping! The most valuable contributions:

- **New packs** — convert one and PR the tarball + its `LIBRARY` entry. See
  [docs/ADD_YOUR_PACK.md](docs/ADD_YOUR_PACK.md).
- **New models** — got a different Trouver/Dreame/Mova? Transcribe its official pack and PR an
  `app/data/<model>_events.json` + a bridge mapping. See [docs/HOW_IT_WORKS.md](docs/HOW_IT_WORKS.md).
- **Better mappings** — if a pack voices more events on your model, improve the map.
- **Translations / docs / screenshots** — always welcome.

## Ground rules

- Don't commit secrets. `secret.env`, `session.json` and tokens are git‑ignored — keep it that way.
- Credit pack authors in [docs/CREDITS.md](docs/CREDITS.md).
- Keep packs small (8 kbps) so they install reliably.

## Dev setup

```bash
./run.sh   # venv + deps + server on :8765
```

The backend is a single Flask app (`app/server.py`); the UI is vanilla HTML/CSS/JS in `app/static/`.
No build step.
