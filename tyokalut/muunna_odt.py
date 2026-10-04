#!/usr/bin/env python3
"""Muuntaa laatukäsikirjan Markdown-dokumentit muotoiltuiksi ODT-tiedostoiksi.

Käyttö:  python3 tyokalut/muunna_odt.py [tiedosto.md ...]
Ilman argumentteja muunnetaan kaikki laatukasikirja/*.md -tiedostot.

Vaatii pandocin (komentona `pandoc` tai Python-pakettina `pypandoc_binary`).
"""
import pathlib
import re
import shutil
import subprocess
import sys
import zipfile
from xml.sax.saxutils import escape

ROOT = pathlib.Path(__file__).resolve().parent.parent
ORG = "OddOneOut ry"
SERIES = "Laatukäsikirja"

# Ulkoasu
FONT = "Liberation Sans"
ACCENT = "#1F3A5F"      # tumma sininen: otsikot, taulukon otsikkorivi
ACCENT_2 = "#2E5C8A"    # vaaleampi sininen: alaotsikot
RULE = "#B7C3D0"        # taulukon reunat ja viivat
SHADE = "#F2F5F9"       # liitepohjien tausta
MUTED = "#5A6472"       # ylä- ja alatunnisteen teksti
PAGE_W, PAGE_H, MARGIN_X = 21.0, 29.7, 2.2  # A4, cm
TEXT_W = PAGE_W - 2 * MARGIN_X


def find_pandoc():
    exe = shutil.which("pandoc")
    if exe:
        return exe
    try:
        import pypandoc
        return pypandoc.get_pandoc_path()
    except Exception:
        sys.exit("pandoc puuttuu: asenna pandoc tai `pip install pypandoc_binary`")


# --- Markdownin esikäsittely -------------------------------------------------

SEP = re.compile(r"^\s*(>\s*)?\|(\s*:?-+:?\s*\|)+\s*$")


def _cells(line):
    return [c.strip() for c in re.sub(r"^\s*>?\s*", "", line).strip().strip("|").split("|")]


def _plain(text):
    return re.sub(r"[*_`\[\]]", "", text)


def prepare(md):
    """Poistaa HTML-kommentit ja mitoittaa taulukoiden sarakkeet sisällön mukaan."""
    md = re.sub(r"<!--.*?-->\n*", "", md, flags=re.S)
    lines = md.split("\n")
    i = 0
    while i < len(lines):
        if not SEP.match(lines[i]):
            i += 1
            continue
        prefix = "> " if lines[i].lstrip().startswith(">") else ""
        rows, j = [_cells(lines[i - 1])], i + 1
        while j < len(lines) and lines[j].strip().lstrip(">").strip().startswith("|"):
            rows.append(_cells(lines[j]))
            j += 1
        widths = []
        for k in range(len(rows[0])):
            col = [_plain(r[k]) if k < len(r) else "" for r in rows]
            longest_word = max((len(w) for c in col for w in c.split()), default=4)
            avg = sum(len(c) for c in col) / len(col)
            widths.append(max(longest_word + 2, min(int(avg), 48), 6))
        lines[i] = prefix + "|" + "|".join("-" * w for w in widths) + "|"
        i = j
    return "\n".join(lines)


def metadata(md):
    def field(name, default):
        m = re.search(r"^\|\s*\*\*" + re.escape(name) + r"\*\*\s*\|\s*(.*?)\s*\|", md, re.M)
        return m.group(1) if m else default

    title = re.search(r"^# (.+)$", md, re.M).group(1).strip()
    doc_id = field("Dokumentin tunnus", "")
    if doc_id.startswith("[esim."):
        doc_id = "[Tunnus]"
    return {
        "title": title,
        "id": doc_id,
        "version": field("Versio", ""),
        "status": field("Tila", ""),
    }


# --- Tyylit ------------------------------------------------------------------

def _set_style(xml, name, new):
    pat = re.compile(r'<style:style\b(?=[^>]*style:name="' + re.escape(name) + r'")[^>]*?(/>|>.*?</style:style>)', re.S)
    if pat.search(xml):
        return pat.sub(lambda _: new, xml, count=1)
    return xml.replace("</office:styles>", new + "</office:styles>")


def _pstyle(name, display, parent, para="", text="", extra_attrs="", tabs=()):
    inner = ""
    if tabs:
        inner = "<style:tab-stops>" + "".join(
            f'<style:tab-stop style:position="{pos:.2f}cm" style:type="{kind}"/>' for pos, kind in tabs) + "</style:tab-stops>"
    return (f'<style:style style:name="{name}" style:display-name="{display}" style:family="paragraph" '
            f'style:parent-style-name="{parent}" {extra_attrs}>'
            f'<style:paragraph-properties {para}>{inner}</style:paragraph-properties>'
            f'<style:text-properties {text}/></style:style>')


def _font(size=None, weight=None, color=None, style=None):
    attrs = f'style:font-name="{FONT}" style:font-name-asian="{FONT}" style:font-name-complex="{FONT}" '
    if size:
        attrs += f'fo:font-size="{size}" style:font-size-asian="{size}" style:font-size-complex="{size}" '
    if weight:
        attrs += f'fo:font-weight="{weight}" style:font-weight-asian="{weight}" style:font-weight-complex="{weight}" '
    if style:
        attrs += f'fo:font-style="{style}" style:font-style-asian="{style}" style:font-style-complex="{style}" '
    if color:
        attrs += f'fo:color="{color}" '
    return attrs


def style_styles(xml, meta):
    font_decl = (f'<style:font-face style:name="{FONT}" svg:font-family="&apos;{FONT}&apos;" '
                 'style:font-family-generic="swiss" style:font-pitch="variable"/>')
    xml = xml.replace("</office:font-face-decls>", font_decl + "</office:font-face-decls>", 1)

    # Oletuskappale: fontti, koko, suomi + tavutus
    xml = re.sub(r'(<style:default-style style:family="paragraph">.*?<style:text-properties )([^/]*)/>',
                 lambda m: m.group(1) + re.sub(
                     r'style:font-name(-asian|-complex)?="[^"]*"|(fo|style):font-size(-asian|-complex)?="[^"]*"|'
                     r'fo:language="[^"]*"|fo:country="[^"]*"|fo:hyphenate="[^"]*"',
                     "", m.group(2))
                 + f' {_font("10pt")} fo:language="fi" fo:country="FI" fo:hyphenate="true" />',
                 xml, count=1, flags=re.S)

    styles = {
        "Standard": '<style:style style:name="Standard" style:family="paragraph" style:class="text">'
                    f'<style:text-properties {_font("10pt")} fo:color="#1A1A1A"/></style:style>',
        "Text_20_body": _pstyle("Text_20_body", "Text body", "Standard",
                                'fo:margin-top="0.08cm" fo:margin-bottom="0.18cm" fo:line-height="128%" '
                                'fo:orphans="2" fo:widows="2"'),
        "First_20_paragraph": _pstyle("First_20_paragraph", "First paragraph", "Text_20_body"),
        "Heading": _pstyle("Heading", "Heading", "Standard",
                           'fo:keep-with-next="always" fo:margin-top="0.5cm" fo:margin-bottom="0.2cm"',
                           _font("13pt", "bold", ACCENT), 'style:next-style-name="Text_20_body" style:class="text"'),
        "Heading_20_1": _pstyle("Heading_20_1", "Heading 1", "Heading",
                                'fo:margin-top="0cm" fo:margin-bottom="0.45cm" fo:padding-bottom="0.15cm" '
                                f'fo:border-bottom="1.5pt solid {ACCENT}"',
                                _font("22pt", "bold", ACCENT),
                                'style:default-outline-level="1" style:next-style-name="Text_20_body" style:class="text"'),
        "Heading_20_2": _pstyle("Heading_20_2", "Heading 2", "Heading",
                                'fo:margin-top="0.6cm" fo:margin-bottom="0.2cm"',
                                _font("13pt", "bold", ACCENT),
                                'style:default-outline-level="2" style:next-style-name="Text_20_body" style:class="text"'),
        "Heading_20_3": _pstyle("Heading_20_3", "Heading 3", "Heading",
                                'fo:margin-top="0.4cm" fo:margin-bottom="0.15cm"',
                                _font("11pt", "bold", ACCENT_2),
                                'style:default-outline-level="3" style:next-style-name="Text_20_body" style:class="text"'),
        "Table_20_Contents": _pstyle("Table_20_Contents", "Table Contents", "Standard",
                                     'fo:margin-top="0cm" fo:margin-bottom="0cm" fo:line-height="118%"',
                                     _font("9pt"), 'style:class="extra"'),
        "Table_20_Heading": _pstyle("Table_20_Heading", "Table Heading", "Table_20_Contents",
                                    'fo:text-align="start"', _font("9pt", "bold", "#FFFFFF"), 'style:class="extra"'),
        "Quotations": _pstyle("Quotations", "Quotations", "Standard",
                              'fo:margin-left="0cm" fo:margin-right="0cm" fo:margin-top="0cm" fo:margin-bottom="0cm" '
                              f'fo:line-height="128%" fo:background-color="{SHADE}" fo:padding-left="0.35cm" '
                              'fo:padding-right="0.3cm" fo:padding-top="0.12cm" fo:padding-bottom="0.12cm" '
                              f'fo:border-left="2.5pt solid {ACCENT_2}" fo:border-right="none" fo:border-top="none" '
                              'fo:border-bottom="none" style:join-border="true"',
                              _font("9.5pt"), 'style:class="html"'),
        "Page_20_Break": _pstyle("Page_20_Break", "Page Break", "Standard",
                                 'fo:break-after="page" fo:margin-top="0cm" fo:margin-bottom="0cm"',
                                 'fo:font-size="2pt"'),
        "Header": _pstyle("Header", "Header", "Standard",
                          f'fo:padding-bottom="0.12cm" fo:border-bottom="0.75pt solid {RULE}"',
                          _font("8pt", color=MUTED), 'style:class="extra"', tabs=[(TEXT_W, "right")]),
        "Footer": _pstyle("Footer", "Footer", "Standard",
                          f'fo:padding-top="0.12cm" fo:border-top="0.75pt solid {RULE}"',
                          _font("8pt", color=MUTED), 'style:class="extra"',
                          tabs=[(TEXT_W / 2, "center"), (TEXT_W, "right")]),
        "Strong_20_Emphasis": '<style:style style:name="Strong_20_Emphasis" style:display-name="Strong Emphasis" '
                              'style:family="text"><style:text-properties fo:font-weight="bold" '
                              'style:font-weight-asian="bold" style:font-weight-complex="bold"/></style:style>',
    }
    for name, new in styles.items():
        xml = _set_style(xml, name, new)

    # Sivun asettelu (A4) ja ylä-/alatunniste
    layout = (f'<style:page-layout style:name="Mpm1"><style:page-layout-properties fo:page-width="{PAGE_W}cm" '
              f'fo:page-height="{PAGE_H}cm" style:print-orientation="portrait" style:num-format="1" '
              f'fo:margin-top="1.2cm" fo:margin-bottom="1.2cm" fo:margin-left="{MARGIN_X}cm" '
              f'fo:margin-right="{MARGIN_X}cm" style:writing-mode="lr-tb"/>'
              '<style:header-style><style:header-footer-properties fo:min-height="0.8cm" '
              'fo:margin-bottom="0.6cm" style:dynamic-spacing="false"/></style:header-style>'
              '<style:footer-style><style:header-footer-properties fo:min-height="0.8cm" '
              'fo:margin-top="0.6cm" style:dynamic-spacing="false"/></style:footer-style></style:page-layout>')
    xml = re.sub(r'<style:page-layout style:name="Mpm1">.*?</style:page-layout>', lambda _: layout, xml, flags=re.S)

    right = escape(" | ".join(x for x in (meta["id"], meta["title"]) if x))
    ver = escape(" · ".join(x for x in (f'Versio {meta["version"]}' if meta["version"] else "", meta["status"]) if x))
    master = ('<style:master-page style:name="Standard" style:page-layout-name="Mpm1">'
              f'<style:header><text:p text:style-name="Header"><text:span text:style-name="MT1">{escape(ORG)}</text:span>'
              f' – {escape(SERIES)}<text:tab/>{right}</text:p></style:header>'
              f'<style:footer><text:p text:style-name="Footer">{ver}<text:tab/>Tulostettu kopio on ohjaamaton'
              '<text:tab/>Sivu <text:page-number text:select-page="current">1</text:page-number> / '
              '<text:page-count>1</text:page-count></text:p></style:footer></style:master-page>')
    xml = re.sub(r'<style:master-page style:name="Standard".*?</style:master-page>', lambda _: master, xml, flags=re.S)
    xml = xml.replace("</office:automatic-styles>",
                      f'<style:style style:name="MT1" style:family="text"><style:text-properties fo:font-weight="bold" '
                      f'fo:color="{ACCENT}"/></style:style></office:automatic-styles>', 1)
    return xml


def style_content(xml):
    border = f'fo:border="0.5pt solid {RULE}" fo:padding-left="0.14cm" fo:padding-right="0.14cm" fo:padding-top="0.08cm" fo:padding-bottom="0.08cm"'
    xml = re.sub(r'(<style:style style:name="TableHeaderRowCell" style:family="table-cell">\s*)<style:table-cell-properties[^>]*/>',
                 lambda m: m.group(1) + f'<style:table-cell-properties {border} fo:background-color="{ACCENT}" style:vertical-align="middle"/>', xml)
    xml = re.sub(r'(<style:style style:name="TableRowCell" style:family="table-cell">\s*)<style:table-cell-properties[^>]*/>',
                 lambda m: m.group(1) + f'<style:table-cell-properties {border} style:vertical-align="top"/>', xml)
    xml = re.sub(r'<style:table-properties table:align="center"\s*/>',
                 f'<style:table-properties table:align="margins" style:width="{TEXT_W}cm" '
                 'fo:margin-top="0.12cm" fo:margin-bottom="0.3cm" style:may-break-between-rows="true"/>', xml)
    # Taulukon rivi ei katkea kahdelle sivulle
    xml = xml.replace("<table:table-row>", '<table:table-row table:style-name="KeepRow">')
    xml = xml.replace("</office:automatic-styles>",
                      '<style:style style:name="KeepRow" style:family="table-row">'
                      '<style:table-row-properties fo:keep-together="always"/></style:style></office:automatic-styles>', 1)
    # Lainauslohkojen sisennys tulee tyylistä
    xml = re.sub(r'(style:parent-style-name="Quotations">\s*<style:paragraph-properties )[^/]*/>',
                 r'\1fo:margin-left="0cm" fo:margin-right="0cm"/>', xml)
    # Vaakaviiva = sivunvaihto (kansilehti ja liitteet omille sivuilleen)
    xml = re.sub(r'<text:p text:style-name="Horizontal_20_Line"\s*/>',
                 '<text:p text:style-name="Page_20_Break"/>', xml)
    return xml


def convert(src, pandoc):
    md = src.read_text(encoding="utf-8")
    out = src.with_suffix(".odt")
    subprocess.run([pandoc, "-f", "markdown-smart-yaml_metadata_block", "-t", "odt", "--columns=20",
                    "-M", "lang=fi-FI", "-o", str(out)],
                   input=prepare(md), text=True, check=True)
    meta = metadata(md)
    tmp = out.with_suffix(".tmp")
    with zipfile.ZipFile(out) as zin, zipfile.ZipFile(tmp, "w") as zout:
        for item in zin.infolist():
            data = zin.read(item.filename)
            if item.filename == "styles.xml":
                data = style_styles(data.decode("utf-8"), meta).encode("utf-8")
            elif item.filename == "content.xml":
                data = style_content(data.decode("utf-8")).encode("utf-8")
            compress = zipfile.ZIP_STORED if item.filename == "mimetype" else zipfile.ZIP_DEFLATED
            zout.writestr(item, data, compress_type=compress)
    tmp.replace(out)
    print(f"{src.relative_to(ROOT)} -> {out.relative_to(ROOT)}")


def main():
    pandoc = find_pandoc()
    files = [pathlib.Path(a).resolve() for a in sys.argv[1:]] or sorted((ROOT / "laatukasikirja").glob("*.md"))
    for f in files:
        convert(f, pandoc)


if __name__ == "__main__":
    main()
