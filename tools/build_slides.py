"""Build slides/index.html from slides/src/*.html (Python 3.10+ standard library).

    python tools/build_slides.py                 # assemble slides/index.html
    python tools/build_slides.py --fonts DIR     # also subset fonts from DIR (needs fonttools+brotli)

Source conventions (slides/src/):
  _template.html          page shell; contains <!-- SLIDES --> and {{TOTAL}}
  NN-name.html            slide partials, concatenated in file-name order

Code blocks are written raw (no HTML escaping needed) and highlighted at build time:
  <script type="text/x-code" data-lang="json" data-title="opencode.json" data-mark="3-5">
  { "mcp": { ... } }
  </script>
"""
from __future__ import annotations

import html
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "slides" / "src"
OUT = ROOT / "slides" / "index.html"
FONT_DIR = ROOT / "slides" / "assets" / "fonts"

for _stream in (sys.stdout, sys.stderr):
    try:
        _stream.reconfigure(encoding="utf-8")
    except AttributeError:
        pass

CODE_RE = re.compile(r'<script type="text/x-code"([^>]*)>\n?(.*?)\n?[ \t]*</script>', re.S)
ATTR_RE = re.compile(r'([\w-]+)="([^"]*)"')

# ---------------------------------------------------------------- highlighting
TOKEN_RULES: dict[str, list[tuple[str, str]]] = {
    "json": [
        (r'"(?:\\.|[^"\\])*"(?=\s*:)', "key"),
        (r'"(?:\\.|[^"\\])*"', "str"),
        (r"//[^\n]*", "com"),
        (r"\b(?:true|false|null)\b", "kw"),
        (r"-?\b\d+(?:\.\d+)?\b", "num"),
    ],
    "js": [
        (r"//[^\n]*|(?s:/\*.*?\*/)", "com"),
        (r"`(?:\\.|[^`\\])*`|\"(?:\\.|[^\"\\])*\"|'(?:\\.|[^'\\])*'", "str"),
        (r"\b(?:import|from|export|default|const|let|var|async|await|function|return|if|else|for|of|in|throw|new|try|catch|typeof|true|false|null|undefined)\b", "kw"),
        (r"\b\d+(?:\.\d+)?\b", "num"),
    ],
    "python": [
        (r"#[^\n]*", "com"),
        (r'"""(?:.|\n)*?"""|\'\'\'(?:.|\n)*?\'\'\'|f?"(?:\\.|[^"\\])*"|f?\'(?:\\.|[^\'\\])*\'', "str"),
        (r"\b(?:def|class|import|from|return|if|elif|else|for|while|in|not|and|or|with|as|try|except|raise|None|True|False|lambda|yield|async|await|pass|break|continue)\b", "kw"),
        (r"\b\d+(?:\.\d+)?\b", "num"),
    ],
    "shell": [
        (r"(?m:^\s*#[^\n]*)", "com"),
        (r'"(?:\\.|[^"\\])*"|\'[^\']*\'', "str"),
        (r"(?m:^(?:PS [^>]*>|\$|>)(?= ))", "prompt"),
        (r"\$env:\w+|\$\w+|%\w+%", "var"),
        (r"(?<![\w-])--?[a-zA-Z][\w-]*", "flag"),
    ],
    "md": [
        (r"(?m:^---$)", "com"),
        (r"(?m:^#{1,6} [^\n]*)", "kw"),
        (r"(?m:^[\w-]+(?=:))", "key"),
        (r"`[^`\n]+`", "str"),
    ],
    "yaml": [
        (r"#[^\n]*", "com"),
        (r"(?m:^\s*[\w.-]+(?=:))", "key"),
        (r'"(?:\\.|[^"\\])*"', "str"),
    ],
    "text": [],
}
TOKEN_RULES["jsonc"] = TOKEN_RULES["json"]
TOKEN_RULES["ts"] = TOKEN_RULES["js"]
TOKEN_RULES["powershell"] = TOKEN_RULES["shell"]
TOKEN_RULES["bash"] = TOKEN_RULES["shell"]


def highlight(code: str, lang: str) -> str:
    rules = TOKEN_RULES.get(lang, [])
    if not rules:
        return html.escape(code, quote=False)
    pattern = re.compile("|".join(f"(?P<g{i}>{rx})" for i, (rx, _) in enumerate(rules)))
    out, pos = [], 0
    for m in pattern.finditer(code):
        out.append(html.escape(code[pos:m.start()], quote=False))
        cls = rules[int(m.lastgroup[1:])][1]
        out.append(f'<span class="t-{cls}">{html.escape(m.group(0), quote=False)}</span>')
        pos = m.end()
    out.append(html.escape(code[pos:], quote=False))
    return "".join(out)


def mark_lines(highlighted: str, spec: str) -> str:
    marked: set[int] = set()
    for part in filter(None, (p.strip() for p in spec.split(","))):
        a, _, b = part.partition("-")
        marked.update(range(int(a), int(b or a) + 1))
    lines = highlighted.split("\n")
    return "\n".join(f'<span class="hl">{ln}</span>' if i + 1 in marked else ln for i, ln in enumerate(lines))


def dedent(code: str) -> str:
    lines = code.split("\n")
    indents = [len(l) - len(l.lstrip(" ")) for l in lines if l.strip()]
    cut = min(indents, default=0)
    return "\n".join(l[cut:] for l in lines).strip("\n")


def render_code(match: re.Match) -> str:
    attrs = dict(ATTR_RE.findall(match.group(1)))
    lang = attrs.get("data-lang", "text")
    code = dedent(match.group(2))
    body = highlight(code, lang)
    if attrs.get("data-mark"):
        body = mark_lines(body, attrs["data-mark"])
    extra = attrs.get("class", "")
    title = attrs.get("data-title")
    cap = f"<figcaption>{html.escape(title)}</figcaption>" if title else ""
    return f'<figure class="code {extra}" data-lang="{lang}">{cap}<pre><code>{body}</code></pre></figure>'


# ---------------------------------------------------------------- build
DIAGRAM_RE = re.compile(r'<x-diagram(?: focus="([^"]*)")?(?: class="([^"]*)")?\s*></x-diagram>')


def render_diagram(match: re.Match) -> str:
    """<x-diagram focus="skill mcp"></x-diagram> → the wiring diagram with other parts dimmed."""
    svg = (SRC / "_diagram.svg").read_text(encoding="utf-8").strip()
    focus = set((match.group(1) or "").split())
    if focus:
        def dim(m: re.Match) -> str:
            part = m.group(1)
            keep = part in focus or part in ("core", "model")
            return m.group(0) if keep else f'<g data-part="{part}" class="dim">'
        svg = re.sub(r'<g data-part="(\w+)">', dim, svg)
    if match.group(2):
        svg = svg.replace('class="diagram wiring"', f'class="diagram wiring {match.group(2)}"', 1)
    return svg


def build() -> str:
    template = (SRC / "_template.html").read_text(encoding="utf-8")
    parts = [p.read_text(encoding="utf-8") for p in sorted(SRC.glob("[0-9]*.html"))]
    slides = DIAGRAM_RE.sub(render_diagram, "\n".join(parts))
    slides = CODE_RE.sub(render_code, slides)
    total = len(re.findall(r'<section class="slide', slides))
    page = template.replace("<!-- SLIDES -->", slides).replace("{{TOTAL}}", str(total))
    OUT.write_text(page, encoding="utf-8")
    print(f"wrote {OUT.relative_to(ROOT)} ({total} slides)")
    return page


# ---------------------------------------------------------------- fonts
FONTS = [
    # (source file, output stem, new family name, weight)
    ("ibmplexsanskr-IBMPlexSansKR-Regular.ttf", "seminar-sans-400", "Seminar Sans KR", 400),
    ("ibmplexsanskr-IBMPlexSansKR-SemiBold.ttf", "seminar-sans-600", "Seminar Sans KR", 600),
    ("ibmplexsanskr-IBMPlexSansKR-Bold.ttf", "seminar-sans-700", "Seminar Sans KR", 700),
    ("ibmplexmono-IBMPlexMono-Regular.ttf", "seminar-mono-400", "Seminar Mono", 400),
    ("ibmplexmono-IBMPlexMono-SemiBold.ttf", "seminar-mono-600", "Seminar Mono", 600),
]


def subset_fonts(page: str, src_dir: Path) -> None:
    """Subset to the characters used in the deck and rename the family (OFL Reserved Font Name)."""
    from fontTools import subset
    from fontTools.ttLib import TTFont

    text = html.unescape(re.sub(r"<[^>]+>", " ", page))
    chars = set(text) | set(chr(c) for c in range(0x20, 0x7F)) | set("·…“”‘’→←↑↓✓✗⚙•—–")
    FONT_DIR.mkdir(parents=True, exist_ok=True)
    for src, stem, family, weight in FONTS:
        font = TTFont(src_dir / src)
        opts = subset.Options()
        opts.flavor = "woff2"
        opts.layout_features = ["*"]
        opts.name_IDs = ["*"]
        sub = subset.Subsetter(opts)
        sub.populate(text="".join(chars))
        sub.subset(font)
        style = {400: "Regular", 600: "SemiBold", 700: "Bold"}[weight]
        for rec in font["name"].names:
            if rec.nameID in (1, 16):
                rec.string = family
            elif rec.nameID == 4:
                rec.string = f"{family} {style}"
            elif rec.nameID == 6:
                rec.string = f"{family.replace(' ', '')}-{style}"
            elif rec.nameID == 3:
                rec.string = f"{family.replace(' ', '')}-{style};subset"
        font.flavor = "woff2"
        out = FONT_DIR / f"{stem}.woff2"
        font.save(out)
        print(f"font {out.relative_to(ROOT)} {out.stat().st_size // 1024} KiB")


if __name__ == "__main__":
    page = build()
    if "--fonts" in sys.argv:
        subset_fonts(page, Path(sys.argv[sys.argv.index("--fonts") + 1]))
