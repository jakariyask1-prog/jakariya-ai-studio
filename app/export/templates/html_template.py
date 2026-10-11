"""Self-contained layout shell for exported HTML conversations."""

from __future__ import annotations

import html


def render_html_document(title: str, body: str) -> str:
    """Wrap already-escaped conversation markup in a portable HTML document."""
    safe_title = html.escape(title)
    return f"""<!doctype html>
<html lang="bn">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>{safe_title}</title>
  <style>
    :root {{ color-scheme: light; font-family: "Nirmala UI", "Noto Sans Bengali", Arial, sans-serif; }}
    body {{ margin: 0; background: #f4f7fb; color: #18212f; line-height: 1.55; }}
    main {{ max-width: 900px; margin: 32px auto; padding: 0 20px; }}
    header, article {{ background: #fff; border: 1px solid #dbe3ed; border-radius: 12px; padding: 24px; }}
    header {{ margin-bottom: 18px; }} h1 {{ margin: 0; color: #0b2545; }}
    .meta {{ color: #5b6778; font-size: .9rem; }} article {{ margin: 14px 0; }}
    .role {{ color: #2e74b5; font-size: 1.05rem; font-weight: 700; }}
    pre {{ overflow-x: auto; background: #f1f4f8; border-radius: 8px; padding: 14px; }}
    code {{ font-family: Consolas, "Courier New", monospace; }}
    table {{ border-collapse: collapse; width: 100%; margin: 12px 0; }}
    th, td {{ border: 1px solid #cbd5e1; padding: 8px; text-align: left; vertical-align: top; }}
    th {{ background: #e8eef5; }} img {{ display: block; max-width: 100%; max-height: 520px; margin: 12px 0; }}
    .attachments {{ padding-left: 20px; }} a {{ color: #1d5fa7; }}
  </style>
</head>
<body><main><header><h1>{safe_title}</h1></header>{body}</main></body>
</html>"""
