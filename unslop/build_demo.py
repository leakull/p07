"""
Собирает демо-страницы интерфейса, которые открываются без бэкенда:
    python3 unslop/build_demo.py

unslop/demo/index.html     — новый интерфейс (app/static/index.html)
unslop/demo/original.html  — старый интерфейс (unslop/index.original.html), для сравнения

В каждую страницу перед скриптом приложения вшивается unslop/demo/mock-api.js,
который отвечает на запросы /api/* данными из seed.py в памяти браузера.
"""

from pathlib import Path

HERE = Path(__file__).resolve().parent
MOCK = (HERE / "demo" / "mock-api.js").read_text(encoding="utf-8")
APP_SCRIPT = "<script>\n'use strict';"

PAGES = [
    (HERE.parent / "app" / "static" / "index.html", HERE / "demo" / "index.html"),
    (HERE / "index.original.html", HERE / "demo" / "original.html"),
]

for src, out in PAGES:
    html = src.read_text(encoding="utf-8")
    if APP_SCRIPT not in html:
        raise SystemExit(f"{src}: не найден скрипт приложения")
    html = html.replace(APP_SCRIPT, f"<script>\n{MOCK}\n</script>\n{APP_SCRIPT}", 1)
    out.write_text(html, encoding="utf-8")
    print(f"собрано: {out.relative_to(HERE.parent)}")
