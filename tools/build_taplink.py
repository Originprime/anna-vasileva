"""Собирает index.html в один фрагмент для блока «HTML-код» в Taplink.

Сайт кладётся в Shadow DOM: стили Taplink не ломают сайт и наоборот.
Запуск:  python3 tools/build_taplink.py   →  taplink/taplink-vstavka.html
"""
import base64, json, pathlib, re, subprocess, tempfile

ROOT = pathlib.Path(__file__).resolve().parent.parent
src = (ROOT / "index.html").read_text(encoding="utf-8")

def between(text, start, end):
    i = text.index(start) + len(start)
    return text[i:text.index(end, i)]

# ---------- CSS: страница → контейнер .av-root
css = between(src, "<style>", "</style>")
css = css.replace(":root{", ".av-root{")
css = re.sub(r"html\{[^}]*\}", "", css)
css = re.sub(r"(?<![\w.-])body\{", ".av-root{", css)  # только тег body, не класс .body
css = ":host{display:block;all:initial}\n" + css

# ---------- разметка
body = between(src, "<body>", "<script>\n(function(){")
# svg-спрайт → встраиваем иконки прямо в каждую ссылку
sprite = between(body, '<svg width="0" height="0"', "</svg>\n")
symbols = dict(
    (m.group(1), (m.group(2), m.group(3)))
    for m in re.finditer(r'<symbol id="([^"]+)" viewBox="([^"]+)">(.*?)</symbol>', sprite, re.S)
)
body = body.replace('<svg width="0" height="0"' + sprite + "</svg>\n", "")
def inline_icon(m):
    attrs, ref = m.group(1), m.group(2)
    vb, inner = symbols[ref]
    return f'<svg{attrs} viewBox="{vb}" aria-hidden="true">{inner}</svg>'
body = re.sub(r'<svg([^>]*)><use href="#([^"]+)"/></svg>', inline_icon, body)

# фото → внутрь кода (jpeg, чтобы было легче)
png = ROOT / "img" / "anna-vasileva.png"
with tempfile.TemporaryDirectory() as tmp:
    jpg = pathlib.Path(tmp) / "a.jpg"
    subprocess.run(["sips", "-s", "format", "jpeg", "-s", "formatOptions", "85", str(png), "--out", str(jpg)],
                   check=True, capture_output=True)
    data = base64.b64encode(jpg.read_bytes()).decode()
body = body.replace('src="img/anna-vasileva.png"', f'src="data:image/jpeg;base64,{data}"')

template = f"<style>{css}</style><div class=\"av-root\">{body}</div>"

# ---------- скрипт: document → shadow root, без работы с адресной строкой
js = between(src, "<script>\n(function(){", "})();\n</script>\n</body>")
js = js.replace("a.addEventListener('click',function(e){e.preventDefault();open(a.dataset.doc);history.replaceState(null,'','#'+a.dataset.doc);});",
                "a.addEventListener('click',function(e){e.preventDefault();open(a.dataset.doc);});")
js = js.replace("d.addEventListener('close',function(){document.body.style.overflow='';history.replaceState(null,'',location.pathname);});",
                "d.addEventListener('close',function(){document.body.style.overflow='';});")
js = js.replace("  if(location.hash)open(location.hash.slice(1));\n", "")
js = js.replace("document.body", "__BODY__")
js = js.replace("document.getElementById", "R.getElementById").replace("document.querySelectorAll", "R.querySelectorAll")
js = js.replace("__BODY__", "document.body")
assert "history." not in js and "location." not in js, "остались обращения к адресной строке"
assert "document.get" not in js and "document.query" not in js, "остались обращения к document"

fonts = re.search(r'<link href="(https://fonts.googleapis.com/[^"]+)" rel="stylesheet">', src).group(1)

out = f"""<!-- Сайт Анны Васильевой для Taplink: вставить ЦЕЛИКОМ в блок «HTML-код». Собрано из index.html -->
<div id="av-site"></div>
<script>
(function(){{
  var host=document.getElementById('av-site');
  if(!host||host.shadowRoot)return;
  if(!document.getElementById('av-fonts')){{var l=document.createElement('link');l.id='av-fonts';l.rel='stylesheet';l.href={json.dumps(fonts)};document.head.appendChild(l);}}
  var R=host.attachShadow({{mode:'open'}});
  R.innerHTML={json.dumps(template, ensure_ascii=False)};
  R.querySelector('.av-root').classList.add('js');
{js}}})();
</script>
"""
dest = ROOT / "taplink" / "taplink-vstavka.html"
dest.parent.mkdir(exist_ok=True)
dest.write_text(out, encoding="utf-8")
print(dest, f"{len(out.encode('utf-8'))/1024:.1f} КБ")
