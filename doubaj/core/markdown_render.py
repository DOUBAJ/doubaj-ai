"""Markdown → HTML (chat display, HTML/PDF export) with syntax highlighting and RTL detection."""
from __future__ import annotations

import html
import re

import markdown
from pygments.formatters import HtmlFormatter

_ARABIC = re.compile(r"[\u0600-\u06FF\u0750-\u077F\u08A0-\u08FF\uFB50-\uFDFF\uFE70-\uFEFF]")
_LATEX_BLOCK = re.compile(r"\$\$(.+?)\$\$", re.S)
_LATEX_INLINE = re.compile(r"(?<![\\$])\$([^$\n]+?)\$")


def is_rtl(text: str) -> bool:
    letters = [c for c in text[:600] if c.isalpha()]
    if not letters:
        return False
    ar = sum(1 for c in letters if _ARABIC.match(c))
    return ar / len(letters) > 0.3


def pygments_css(dark: bool) -> str:
    style = "monokai" if dark else "friendly"
    return HtmlFormatter(style=style).get_style_defs(".codehilite")


_SYMBOLS = {r"\times": "×", r"\cdot": "·", r"\div": "÷", r"\pm": "±", r"\leq": "≤", r"\geq": "≥",
            r"\neq": "≠", r"\approx": "≈", r"\infty": "∞", r"\sqrt": "√", r"\pi": "π", r"\alpha": "α",
            r"\beta": "β", r"\gamma": "γ", r"\delta": "δ", r"\Delta": "Δ", r"\theta": "θ", r"\lambda": "λ",
            r"\mu": "μ", r"\omega": "ω", r"\Omega": "Ω", r"\phi": "φ", r"\varphi": "φ", r"\sigma": "σ",
            r"\sum": "∑", r"\int": "∫", r"\rightarrow": "→", r"\to": "→", r"\Rightarrow": "⇒", r"\eta": "η",
            r"\rho": "ρ", r"\tau": "τ", r"\epsilon": "ε", r"\partial": "∂", r"\circ": "°", r"\%": "%"}


def _latex_to_text(expr: str) -> str:
    """Very light LaTeX prettifier (the chat view has no TeX engine)."""
    s = expr
    s = re.sub(r"\\frac\{([^{}]*)\}\{([^{}]*)\}", r"(\1)/(\2)", s)
    s = re.sub(r"\\sqrt\{([^{}]*)\}", r"√(\1)", s)
    s = re.sub(r"\\(text|mathrm|mathbf|operatorname)\{([^{}]*)\}", r"\2", s)
    for k in sorted(_SYMBOLS, key=len, reverse=True):
        s = s.replace(k, _SYMBOLS[k])
    s = re.sub(r"\^\{([^{}]*)\}", r"<sup>\1</sup>", s)
    s = re.sub(r"\^(\w)", r"<sup>\1</sup>", s)
    s = re.sub(r"_\{([^{}]*)\}", r"<sub>\1</sub>", s)
    s = re.sub(r"_(\w)", r"<sub>\1</sub>", s)
    s = s.replace("\\left", "").replace("\\right", "").replace("\\,", " ").replace("\\ ", " ")
    s = s.replace("{", "").replace("}", "")
    return s


def md_to_html(text: str, math: bool = True) -> str:
    if math:
        text = _LATEX_BLOCK.sub(lambda m: f"\n\n<div class='math'>{_latex_to_text(m.group(1).strip())}</div>\n\n", text)
        text = _LATEX_INLINE.sub(lambda m: f"<span class='math'>{_latex_to_text(m.group(1))}</span>", text)
    return markdown.markdown(
        text,
        extensions=["tables", "fenced_code", "codehilite", "sane_lists", "nl2br"],
        extension_configs={"codehilite": {"guess_lang": False, "css_class": "codehilite"}},
        output_format="html5",
    )


def wrap_document(body_html: str, title: str = "", rtl: bool = False, dark: bool = False) -> str:
    direction = "rtl" if rtl else "ltr"
    return f"""<!DOCTYPE html>
<html lang="{'ar' if rtl else 'fr'}" dir="{direction}"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{html.escape(title)}</title>
<style>
body {{ font-family: 'Segoe UI', 'Amiri', 'Sakkal Majalla', Arial, sans-serif; max-width: 860px; margin: 32px auto;
       padding: 0 20px; line-height: 1.6; color: #1d2433; }}
h1,h2,h3 {{ color: #0f3d5c; }}
table {{ border-collapse: collapse; margin: 12px 0; }}
th, td {{ border: 1px solid #c8d1dc; padding: 6px 10px; }}
th {{ background: #eef3f8; }}
pre {{ background: #f5f7fa; padding: 12px; border-radius: 6px; overflow-x: auto; direction: ltr; text-align: left; }}
code {{ font-family: Consolas, 'Cascadia Code', monospace; }}
.math {{ font-style: italic; font-family: 'Cambria Math', 'Times New Roman', serif; }}
{pygments_css(dark)}
</style></head><body>
{body_html}
</body></html>"""
