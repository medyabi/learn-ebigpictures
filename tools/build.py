#!/usr/bin/env python3
"""Builds learn.ebigpictures.com from the two lab repositories.

Usage: python3 build.py <hybrid-repo> <security-repo> <output-dir>
"""
import html
import os
import posixpath
import re
import shutil
import sys

import markdown

HYB, SEC, OUT = (os.path.abspath(p) for p in sys.argv[1:4])
GH = {
    "hyb": "https://github.com/medyabi/windows-server2025-Hybrid-lab/blob/main/",
    "sec": "https://github.com/medyabi/windows-server-security-lab/blob/main/",
}
REPO_URL = {
    "hyb": "https://github.com/medyabi/windows-server2025-Hybrid-lab",
    "sec": "https://github.com/medyabi/windows-server-security-lab",
}
ROOTS = {"hyb": HYB, "sec": SEC}

# --------------------------------------------------------------------------
# 1. Which source files become which pages
# --------------------------------------------------------------------------
pages = {}  # (repo, src_rel) -> out_rel


def add(repo, src, out):
    pages[(repo, src)] = out


add("hyb", "README.md", "hybrid/index.html")
for f in sorted(os.listdir(os.path.join(HYB, "labs"))):
    if f.endswith(".md"):
        add("hyb", f"labs/{f}", f"hybrid/{f[:-3]}.html")

add("sec", "README.md", "security/index.html")
add("sec", "docs/00-welcome-and-lab-setup.md", "security/setup.html")
add("sec", "docs/attack-to-control-map.md", "security/attack-to-control-map.html")
add("sec", "docs/progress-checklist.md", "security/progress.html")
for ch in sorted(os.listdir(os.path.join(SEC, "labs"))):
    d = os.path.join(SEC, "labs", ch)
    if not os.path.isdir(d):
        continue
    for f in sorted(os.listdir(d)):
        if not f.endswith(".md"):
            continue
        out = f"security/{ch}/index.html" if f == "README.md" else f"security/{ch}/{f[:-3]}.html"
        add("sec", f"labs/{ch}/{f}", out)


def first_h1(path):
    with open(path, encoding="utf-8") as fh:
        for line in fh:
            if line.startswith("# "):
                return line[2:].strip()
    return os.path.basename(path)


titles = {k: first_h1(os.path.join(ROOTS[k[0]], k[1])) for k in pages}

# --------------------------------------------------------------------------
# 2. Navigation for each track
# --------------------------------------------------------------------------
def short(t):
    return re.sub(r"\s*\((\d+ min[^)]*|[^)]*min[^)]*)\)$", "", t)


hyb_nav = [("Overview", "hybrid/index.html")]
for (repo, src), out in sorted(pages.items(), key=lambda kv: kv[1]):
    if repo == "hyb" and src.startswith("labs/") and "cleanup" not in src:
        hyb_nav.append((short(titles[(repo, src)]), out))
hyb_nav.append(("Cleanup and reset", "hybrid/cleanup-and-reset.html"))

sec_nav = [("Overview", "security/index.html"), ("Lab setup", "security/setup.html")]
sec_groups = []
for ch in sorted(os.listdir(os.path.join(SEC, "labs"))):
    if not os.path.isdir(os.path.join(SEC, "labs", ch)):
        continue
    chap = ("sec", f"labs/{ch}/README.md")
    items = []
    for (repo, src), out in sorted(pages.items(), key=lambda kv: kv[1]):
        if repo == "sec" and src.startswith(f"labs/{ch}/lab-"):
            items.append((titles[(repo, src)].replace("Lab ", ""), out))
    sec_groups.append((titles[chap], pages[chap], items))
sec_tail = [("Attack → control map", "security/attack-to-control-map.html"),
            ("Progress checklist", "security/progress.html")]

# --------------------------------------------------------------------------
# 3. Rendering helpers
# --------------------------------------------------------------------------
def rel(from_out, to_out):
    r = posixpath.relpath(to_out, posixpath.dirname(from_out) or ".")
    return r


def copy_asset(repo, src_rel):
    """Copy an image from a repo into the site; return its site path."""
    name = f"assets/{repo}/{src_rel.replace('/', '-')}"
    dst = os.path.join(OUT, name)
    os.makedirs(os.path.dirname(dst), exist_ok=True)
    shutil.copyfile(os.path.join(ROOTS[repo], src_rel), dst)
    return name


def rewrite_url(url, repo, src_rel, out_rel, is_img=False):
    if re.match(r"^[a-z]+:", url) or url.startswith("#") or url.startswith("//"):
        return url
    path, _, frag = url.partition("#")
    path = html.unescape(path)
    target = posixpath.normpath(posixpath.join(posixpath.dirname(src_rel), path))
    if is_img:
        if os.path.isfile(os.path.join(ROOTS[repo], target)):
            return rel(out_rel, copy_asset(repo, target))
        return url
    key = (repo, target)
    if key in pages:
        new = rel(out_rel, pages[key])
    else:
        new = GH[repo] + target
    return new + ("#" + frag if frag else "")


md = markdown.Markdown(extensions=["tables", "fenced_code", "sane_lists", "toc"],
                       extension_configs={"toc": {"permalink": False}})


def render_md(repo, src_rel, out_rel):
    with open(os.path.join(ROOTS[repo], src_rel), encoding="utf-8") as fh:
        text = fh.read()
    md.reset()
    body = md.convert(text)
    # links and images
    body = re.sub(r'href="([^"]+)"', lambda m: 'href="%s"' % rewrite_url(m.group(1), repo, src_rel, out_rel), body)
    body = re.sub(r'src="([^"]+)"', lambda m: 'src="%s"' % rewrite_url(m.group(1), repo, src_rel, out_rel, True), body)
    # external links open normally; mark them
    body = re.sub(r'<a href="(https?://[^"]+)"', r'<a href="\1" rel="noopener"', body)
    # mermaid
    body = re.sub(r'<pre><code class="language-mermaid">(.*?)</code></pre>',
                  r'<pre class="mermaid">\1</pre>', body, flags=re.S)
    # task lists
    body = re.sub(r"<li>\[ \]\s*", '<li class="task"><input type="checkbox"> ', body)
    body = re.sub(r"<li>\[[xX]\]\s*", '<li class="task"><input type="checkbox" checked> ', body)
    # drop header rows whose cells are all empty (key/value tables)
    body = re.sub(r"<thead>\s*<tr>(?:\s*<th>\s*</th>)+\s*</tr>\s*</thead>", "", body)
    # wrap tables for horizontal scroll
    body = body.replace("<table>", '<div class="table-wrap"><table>').replace("</table>", "</table></div>")
    # navigation lines at top/bottom of labs: paragraph made only of links and separators
    body = re.sub(r"<p>((?:<a [^>]+>[^<]+</a>\s*(?:·\s*)?)+)</p>",
                  lambda m: '<nav class="pager">' + re.sub(r'\s*·\s*', ' ', m.group(1)) + '</nav>', body)
    return body


# --------------------------------------------------------------------------
# 4. Page shell
# --------------------------------------------------------------------------
FONTS = ('<link rel="preconnect" href="https://fonts.googleapis.com">'
         '<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>'
         '<link href="https://fonts.googleapis.com/css2?family=Newsreader:opsz,wght@6..72,500;6..72,600'
         '&family=IBM+Plex+Sans:wght@400;500;600&family=IBM+Plex+Mono:wght@400;500&display=swap" rel="stylesheet">')

MERMAID = ('<script type="module">import mermaid from "https://cdn.jsdelivr.net/npm/mermaid@10.9.1/dist/mermaid.esm.min.mjs";'
           'const dark = document.documentElement.matches("[data-theme=dark]") || (window.matchMedia("(prefers-color-scheme: dark)").matches && !document.documentElement.matches("[data-theme=light]"));'
           'mermaid.initialize({startOnLoad:true, theme: dark ? "dark" : "neutral", securityLevel:"strict"});</script>')

CHECKLIST_JS = """<script>
(function(){
  var key = 'progress:' + location.pathname;
  var boxes = Array.prototype.slice.call(document.querySelectorAll('li.task input'));
  var saved = {};
  try { saved = JSON.parse(localStorage.getItem(key) || '{}'); } catch (e) {}
  boxes.forEach(function(b, i){
    b.id = 'task-' + i;
    if (saved[i]) b.checked = true;
    b.addEventListener('change', function(){
      saved[i] = b.checked;
      try { localStorage.setItem(key, JSON.stringify(saved)); } catch (e) {}
    });
  });
})();
</script>"""


def sidebar(track, out_rel):
    def link(label, target):
        cur = ' aria-current="page"' if target == out_rel else ""
        return f'<a href="{rel(out_rel, target)}"{cur}>{html.escape(label)}</a>'

    if track == "hybrid":
        items = "".join(f"<li>{link(l, t)}</li>" for l, t in hyb_nav)
        return (f'<nav class="side" aria-label="Hybrid labs"><p class="side-title">Hybrid track</p>'
                f'<ol class="side-list">{items}</ol></nav>')
    parts = [f"<li>{link(l, t)}</li>" for l, t in sec_nav]
    for title, chap_out, items in sec_groups:
        sub = "".join(f"<li>{link(l, t)}</li>" for l, t in items)
        parts.append(f'<li class="group">{link(title, chap_out)}<ol>{sub}</ol></li>')
    parts += [f"<li>{link(l, t)}</li>" for l, t in sec_tail]
    return (f'<nav class="side" aria-label="Security labs"><p class="side-title">Security track</p>'
            f'<ol class="side-list">{"".join(parts)}</ol></nav>')


def shell(out_rel, title, body, track=None, extra=""):
    css = rel(out_rel, "assets/site.css")
    home = rel(out_rel, "index.html")
    hyb = rel(out_rel, "hybrid/index.html")
    sec = rel(out_rel, "security/index.html")
    cur_h = ' aria-current="true"' if track == "hybrid" else ""
    cur_s = ' aria-current="true"' if track == "security" else ""
    side = sidebar(track, out_rel) if track else ""
    layout = "with-side" if track else "plain"
    repo = REPO_URL["hyb" if track == "hybrid" else "sec"] if track else None
    src_link = f'<a href="{repo}" rel="noopener">Source on GitHub</a> · ' if repo else ""
    full_title = f"{title} · Windows Server Labs" if title != "Windows Server Labs" else title
    return f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{html.escape(full_title)}</title>
<meta name="description" content="Hands-on Windows Server 2025 labs: hybrid management with Azure Arc, and Windows Server security.">
{FONTS}
<link rel="stylesheet" href="{css}">
</head>
<body class="track-{track or 'home'}">
<a class="skip" href="#content">Skip to content</a>
<header class="top">
  <a class="brand" href="{home}"><span class="brand-mark" aria-hidden="true"></span>Windows Server Labs</a>
  <nav class="tracks" aria-label="Tracks"><a href="{hyb}"{cur_h}>Hybrid</a><a href="{sec}"{cur_s}>Security</a></nav>
</header>
<div class="layout {layout}">
{side}
<main id="content" class="prose">
{body}
</main>
</div>
<footer class="foot"><p>{src_link}By Mohamed Dyabi, Microsoft Certified Trainer · learn.ebigpictures.com</p>
<p class="small">Lab environments only. Several labs change security settings, lock accounts or force recovery. Never run them on production systems.</p></footer>
{extra}
</body>
</html>
"""


# --------------------------------------------------------------------------
# 5. Home page
# --------------------------------------------------------------------------
n_hyb = sum(1 for (r, s) in pages if r == "hyb" and s.startswith("labs/") and "cleanup" not in s)
n_sec = sum(1 for (r, s) in pages if r == "sec" and "/lab-" in s)


def home_page():
    out = "index.html"
    hyb_items = [(re.sub(r"^Lab \d+:\s*", "", l), t) for l, t in hyb_nav[1:-1]]
    hyb_list = "".join(f'<li><a href="{t}">{html.escape(l)}</a></li>' for l, t in hyb_items)
    sec_items = [(re.sub(r"^Chapter \d+:\s*", "", ti), c, len(it)) for ti, c, it in sec_groups]
    sec_list = "".join(f'<li><a href="{c}">{html.escape(ti)}</a> <span class="count">{n} labs</span></li>'
                       for ti, c, n in sec_items)
    body = f"""
<section class="hero">
  <p class="eyebrow">Windows Server 2025 · Azure Arc · AZ-801</p>
  <h1>Learn Windows Server by doing it, one lab at a time</h1>
  <p class="lede">Two hands-on tracks. In the first, you take an on-premises server and manage it from Azure. In the second, you watch an attack, build the control that stops it, and prove that it works.</p>
</section>

<div class="tracks-grid">
  <article class="track-card hybrid">
    <p class="eyebrow">Track 1 · {n_hyb} labs · about 8 hours</p>
    <h2><a href="hybrid/index.html">Hybrid management with Azure Arc</a></h2>
    <p>One Windows Server 2025 VM per person. Connect it to Azure Arc, unlock the Software Assurance benefits, and use Hotpatch, Azure Policy, Azure Monitor, Change Tracking, Defender for Cloud and Windows Admin Center in Azure. Every lab ends with customer talking points.</p>
    <ol class="mini">{hyb_list}</ol>
    <p><a class="button" href="hybrid/index.html">Start the hybrid track</a></p>
  </article>
  <article class="track-card security">
    <p class="eyebrow">Track 2 · {n_sec} labs · AZ-801</p>
    <h2><a href="security/index.html">Securing Windows Server</a></h2>
    <p>Four VMs, one domain, and an attacker. Each lab shows the attack first, then builds the control that stops it: passwords and lockout, Credential Guard, App Control, Protected Users, RODC, delegation, Sentinel, IPsec and BitLocker.</p>
    <ol class="mini">{sec_list}</ol>
    <p><a class="button" href="security/setup.html">Build the lab and start</a></p>
  </article>
</div>

<section class="how">
  <h2>How every lab works</h2>
  <ol class="how-steps">
    <li><strong>The situation.</strong> A customer question or an attacker's move: why this lab matters.</li>
    <li><strong>The concepts.</strong> Just enough theory, in plain words, with an analogy.</li>
    <li><strong>Step by step.</strong> Build it on your own VM, with the exact commands.</li>
    <li><strong>Prove it.</strong> A verification command or a portal view that shows it works.</li>
    <li><strong>Takeaway.</strong> Talking points for the customer, or the one idea to remember.</li>
  </ol>
</section>

<section class="about">
  <h2>What you need</h2>
  <div class="needs">
    <div><h3>Hybrid track</h3><p>A Windows Server 2025 VM (your instructor provides one), an Azure subscription where you can create a resource group, and about two days.</p></div>
    <div><h3>Security track</h3><p>A Hyper-V host for four Generation 2 VMs with Secure Boot and a virtual TPM, plus Azure and Microsoft 365 trials for the cloud chapters.</p></div>
  </div>
</section>
"""
    return shell(out, "Windows Server Labs", body)


# --------------------------------------------------------------------------
# 6. Build
# --------------------------------------------------------------------------
if os.path.isdir(OUT):
    for name in os.listdir(OUT):
        if name in (".git", "CNAME", "tools", "README.md"):
            continue
        p = os.path.join(OUT, name)
        shutil.rmtree(p) if os.path.isdir(p) else os.remove(p)
os.makedirs(OUT, exist_ok=True)

for (repo, src), out in pages.items():
    body = render_md(repo, src, out)
    track = "hybrid" if repo == "hyb" else "security"
    extra = MERMAID if 'class="mermaid"' in body else ""
    if 'class="task"' in body:
        extra += CHECKLIST_JS
    dst = os.path.join(OUT, out)
    os.makedirs(os.path.dirname(dst), exist_ok=True)
    with open(dst, "w", encoding="utf-8") as fh:
        fh.write(shell(out, titles[(repo, src)], body, track, extra))

with open(os.path.join(OUT, "index.html"), "w", encoding="utf-8") as fh:
    fh.write(home_page())

shutil.copyfile(os.path.join(os.path.dirname(os.path.abspath(__file__)), "site.css"),
                os.path.join(OUT, "assets", "site.css"))
with open(os.path.join(OUT, "CNAME"), "w") as fh:
    fh.write("learn.ebigpictures.com\n")
open(os.path.join(OUT, ".nojekyll"), "w").close()
nf = shell("404.html", "Page not found",
           '<h1>Page not found</h1><p>That page doesn\'t exist. Go back to the <a href="index.html">home page</a>.</p>')
# 404 is served at any path: make its links absolute from the site root
nf = re.sub(r'(href|src)="(?!https?:|/|#)', r'\1="/', nf)
with open(os.path.join(OUT, "404.html"), "w", encoding="utf-8") as fh:
    fh.write(nf)
print(f"{len(pages) + 2} pages written to {OUT}")
