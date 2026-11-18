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


md = markdown.Markdown(extensions=["tables", "pymdownx.superfences", "pymdownx.highlight", "sane_lists", "toc"],
                       extension_configs={"toc": {"permalink": False},
                                          "pymdownx.highlight": {"use_pygments": False}})


def render_md(repo, src_rel, out_rel):
    with open(os.path.join(ROOTS[repo], src_rel), encoding="utf-8") as fh:
        text = fh.read()
    # a closing code fence directly followed by text breaks lists: add a blank line
    out_lines, in_fence = [], False
    lines = text.split("\n")
    for i, line in enumerate(lines):
        out_lines.append(line)
        if re.match(r"^\s*```", line):
            in_fence = not in_fence
            if not in_fence and i + 1 < len(lines) and lines[i + 1].strip():
                out_lines.append("")
    text = "\n".join(out_lines)
    md.reset()
    body = md.convert(text)
    body = re.sub(r'<pre class="highlight">', '<pre>', body)
    # links and images
    body = re.sub(r'href="([^"]+)"', lambda m: 'href="%s"' % rewrite_url(m.group(1), repo, src_rel, out_rel), body)
    body = re.sub(r'src="([^"]+)"', lambda m: 'src="%s"' % rewrite_url(m.group(1), repo, src_rel, out_rel, True), body)
    # external links open normally; mark them
    body = re.sub(r'<a href="(https?://[^"]+)"', r'<a href="\1" rel="noopener"', body)
    # mermaid
    body = re.sub(r'<pre><code class="language-mermaid">(.*?)</code></pre>',
                  r'<pre class="mermaid">\1</pre>', body, flags=re.S)
    # blockquotes -> callouts
    def callout(m):
        inner = m.group(1)
        lead = re.sub(r"<[^>]+>", "", inner[:200]).lower()
        kind = "note"
        if re.search(r"legal|before you start|first|warning|never|do not", lead):
            kind = "important"
        if re.search(r"cost", lead):
            kind = "warning"
        label = {"note": "Note", "important": "Important", "warning": "Warning"}[kind]
        return f'<div class="alert {kind}"><p class="alert-title">{label}</p>{inner}</div>'
    body = re.sub(r"<blockquote>\s*(.*?)\s*</blockquote>", callout, body, flags=re.S)
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
# 4. Page shell (layout inspired by documentation sites: header, breadcrumb,
#    left table of contents, article, right "In this article")
# --------------------------------------------------------------------------
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

SITE_JS = """<script>
(function(){
  // Table of contents: open on wide screens, collapsible on small ones
  var toc = document.querySelector('details.toc');
  if (toc) {
    var mq = window.matchMedia('(min-width: 1024px)');
    var sync = function(){ if (mq.matches) toc.open = true; };
    sync(); if (mq.addEventListener) mq.addEventListener('change', sync);
    var cur = toc.querySelector('[aria-current="page"]');
    if (cur && cur.scrollIntoView && mq.matches) cur.scrollIntoView({block: 'center'});
  }
  // Filter by title
  var f = document.getElementById('toc-filter');
  if (f) f.addEventListener('input', function(){
    var q = f.value.trim().toLowerCase();
    document.querySelectorAll('.toc-list li').forEach(function(li){
      var hit = !q || li.textContent.toLowerCase().indexOf(q) !== -1;
      li.hidden = !hit;
    });
  });
  // Copy buttons on code blocks
  document.querySelectorAll('.codeblock').forEach(function(cb){
    var btn = cb.querySelector('.copy'), code = cb.querySelector('code');
    if (!btn || !code) return;
    btn.addEventListener('click', function(){
      navigator.clipboard.writeText(code.innerText).then(function(){
        btn.textContent = 'Copied'; setTimeout(function(){ btn.textContent = 'Copy'; }, 1500);
      }, function(){ btn.textContent = 'Select and copy'; });
    });
  });
  // Highlight the current section in "In this article"
  var links = document.querySelectorAll('.aside-toc a');
  if (links.length && 'IntersectionObserver' in window) {
    var map = {}; links.forEach(function(a){ map[a.getAttribute('href').slice(1)] = a; });
    var obs = new IntersectionObserver(function(es){
      es.forEach(function(e){ if (e.isIntersecting) {
        links.forEach(function(a){ a.classList.remove('on'); });
        var a = map[e.target.id]; if (a) a.classList.add('on');
      }});
    }, {rootMargin: '0px 0px -75% 0px'});
    Object.keys(map).forEach(function(id){ var h = document.getElementById(id); if (h) obs.observe(h); });
  }
})();
</script>"""

LANG_LABEL = {"powershell": "PowerShell", "kusto": "Kusto", "bash": "Bash", "json": "JSON", "xml": "XML"}

ICONS = {
    "hybrid": '<svg viewBox="0 0 24 24" aria-hidden="true"><path d="M7 18a5 5 0 0 1-.6-9.96A6.5 6.5 0 0 1 18.8 9.1 4.5 4.5 0 0 1 18 18Z" fill="currentColor"/></svg>',
    "security": '<svg viewBox="0 0 24 24" aria-hidden="true"><path d="M12 2 4 5v6c0 5 3.4 9.4 8 11 4.6-1.6 8-6 8-11V5Z" fill="currentColor"/></svg>',
    "ai": '<svg viewBox="0 0 24 24" aria-hidden="true"><path d="M4 4h16a2 2 0 0 1 2 2v9a2 2 0 0 1-2 2h-8l-5 4v-4H4a2 2 0 0 1-2-2V6a2 2 0 0 1 2-2Zm8 2.5c-.4 2.3-1.2 3.1-3.5 3.5 2.3.4 3.1 1.2 3.5 3.5.4-2.3 1.2-3.1 3.5-3.5-2.3-.4-3.1-1.2-3.5-3.5Z" fill="currentColor"/></svg>',
    "access": '<svg viewBox="0 0 24 24" aria-hidden="true"><rect x="3" y="4" width="18" height="12" rx="2" fill="currentColor"/><rect x="8" y="18" width="8" height="2" rx="1" fill="currentColor"/></svg>',
}


def sidebar(track, out_rel):
    def link(label, target):
        cur = ' aria-current="page"' if target == out_rel else ""
        return f'<a href="{rel(out_rel, target)}"{cur}>{html.escape(label)}</a>'

    if track == "hybrid":
        name = "Hybrid management with Azure Arc"
        items = "".join(f"<li>{link(l, t)}</li>" for l, t in hyb_nav)
    else:
        name = "Securing Windows Server"
        parts = [f"<li>{link(l, t)}</li>" for l, t in sec_nav]
        for title, chap_out, its in sec_groups:
            sub = "".join(f"<li>{link(l, t)}</li>" for l, t in its)
            open_ = " open" if out_rel == chap_out or any(t == out_rel for _, t in its) else ""
            parts.append(f'<li class="group"><details{open_}><summary>{html.escape(title)}</summary>'
                         f'<ol><li>{link("Chapter overview", chap_out)}</li>{sub}</ol></details></li>')
        parts += [f"<li>{link(l, t)}</li>" for l, t in sec_tail]
        items = "".join(parts)
    return (f'<details class="toc"><summary>Table of contents</summary>'
            f'<nav aria-label="{name}"><p class="toc-title">{name}</p>'
            f'<input id="toc-filter" class="toc-filter" type="search" placeholder="Filter by title" aria-label="Filter by title">'
            f'<ol class="toc-list">{items}</ol></nav></details>')


def crumbs(out_rel, title, track):
    trail = [("Labs", "index.html")]
    if track == "hybrid":
        trail.append(("Hybrid track", "hybrid/index.html"))
    elif track == "security":
        trail.append(("Security track", "security/index.html"))
        for t, chap_out, its in sec_groups:
            if any(o == out_rel for _, o in its):
                trail.append((re.sub(r"^Chapter (\d+):.*", r"Chapter \1", t), chap_out))
    elif track == "access":
        trail.append(("Lab access", "access/index.html"))
    trail = [(l, t) for l, t in trail if t != out_rel]
    items = "".join(f'<li><a href="{rel(out_rel, t)}">{html.escape(l)}</a></li>' for l, t in trail)
    return f'<nav class="crumbs" aria-label="Breadcrumb"><ol>{items}</ol></nav>'


def enhance(body):
    """Code-block headers with Copy, and the 'In this article' list."""
    def code(m):
        lang = m.group(1) or ""
        label = LANG_LABEL.get(lang, lang.capitalize() if lang else "")
        if not lang:
            nxt = body_ref[0][m.end():m.end() + 400]
            if re.search(r"\b(Get|Set|New|Remove|Add|Install|Invoke|Enable|Disable|Start|Stop|Restart|Test|Import|Export|Update|Register|Grant|Copy)-[A-Z]", nxt):
                label = "PowerShell"
        return (f'<div class="codeblock"><div class="code-head"><span>{label}</span>'
                f'<button type="button" class="copy">Copy</button></div><pre><code{m.group(2)}>')
    body_ref = [body]
    body = re.sub(r'<pre><code(?: class="language-([a-z0-9]+)")?()>', code, body)
    body = re.sub(r'(<div class="codeblock">.*?</code></pre>)', r'\1</div>', body, flags=re.S)
    heads = re.findall(r'<h2 id="([^"]+)">(.*?)</h2>', body)
    if len(heads) < 2:
        heads = re.findall(r'<h3 id="([^"]+)">(.*?)</h3>', body)
    aside = ""
    if len(heads) >= 2:
        lis = "".join(f'<li><a href="#{i}">{re.sub(r"<[^>]+>", "", t)}</a></li>' for i, t in heads)
        aside = f'<aside class="aside-toc" aria-label="In this article"><p>In this article</p><ol>{lis}</ol></aside>'
    return body, aside


def meta_line(body, kind):
    words = len(re.sub(r"<[^>]+>", " ", body).split())
    mins = max(1, round(words / 200))
    return f'<p class="meta"><span>{kind}</span><span>{mins} min read</span></p>'


def shell(out_rel, title, body, track=None, extra="", head="", kind="Article"):
    css = rel(out_rel, "assets/site.css")
    home = rel(out_rel, "index.html")
    nav = [("Hybrid", "hybrid/index.html", "hybrid"), ("Security", "security/index.html", "security"),
           ("Lab access", "https://access.ebigpictures.com/", "access"),
           ("AI Labs", "https://ai.ebigpictures.com/", "ai")]
    cur = ' aria-current="true"'
    nav_html = "".join(f'<a href="{t if t.startswith("http") else rel(out_rel, t)}"{cur if track == k else ""}>{l}</a>' for l, t, k in nav)
    full_title = f"{title} · Windows Server Labs" if title != "Windows Server Labs" else title
    is_doc = track in ("hybrid", "security", "access")
    if is_doc:
        body, aside = enhance(body)
        side = sidebar(track, out_rel) if track in ("hybrid", "security") else ""
        # metadata line right after the first h1
        dur = re.search(r"<h1[^>]*>.*?\s*\((\d+[^)]*min[^)]*)\)\s*</h1>", body)
        if dur:
            body = body.replace(" (" + dur.group(1) + ")</h1>", "</h1>", 1)
        meta = meta_line(body, kind)
        if dur:
            meta = meta.replace("</p>", f"<span>Lab time: {dur.group(1)}</span></p>")
        body = re.sub(r"(</h1>)", lambda m: m.group(1) + meta, body, count=1)
        repo = REPO_URL["hyb" if track == "hybrid" else "sec"] if track in ("hybrid", "security") else None
        edit = f'<p class="source"><a href="{repo}" rel="noopener">View the source on GitHub</a></p>' if repo else ""
        layout = f"""<div class="doc {'has-toc' if side else 'no-toc'}">
{side}
<main id="content" class="article">
{crumbs(out_rel, title, track)}
<article class="prose">
{body}
</article>
{edit}
</main>
{aside}
</div>"""
        extra = SITE_JS + extra
    else:
        layout = f'<main id="content" class="home">\n{body}\n</main>'
    return f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{html.escape(full_title)}</title>
<meta name="description" content="Hands-on Windows Server 2025 labs: hybrid management with Azure Arc, and Windows Server security.">
<link rel="stylesheet" href="{css}">
<link rel="icon" href="{rel(out_rel, 'assets/favicon.svg')}" type="image/svg+xml">
<link rel="icon" href="{rel(out_rel, 'assets/favicon-32.png')}" sizes="32x32" type="image/png">
<link rel="apple-touch-icon" href="{rel(out_rel, 'assets/apple-touch-icon.png')}">
{head}</head>
<body class="t-{track or 'home'}">
<a class="skip" href="#content">Skip to main content</a>
<header class="masthead">
  <a class="brand" href="{home}"><img src="{rel(out_rel, 'assets/favicon.svg')}" alt="" width="24" height="24"><span>Windows Server Labs</span></a>
  <span class="divider" aria-hidden="true"></span>
  <nav class="mainnav" aria-label="Main">{nav_html}</nav>
  <a class="gh" href="https://github.com/medyabi" rel="noopener">GitHub</a>
</header>
{layout}
<footer class="sitefoot">
  <div class="foot-in">
    <div><strong>Windows Server Labs</strong><p>Hands-on labs by Mohamed Dyabi, Microsoft Certified Trainer.</p></div>
    <ul>
      <li><a href="{rel(out_rel, 'hybrid/index.html')}">Hybrid track</a></li>
      <li><a href="{rel(out_rel, 'security/index.html')}">Security track</a></li>
      <li><a href="https://bookings.cloud.microsoft/book/WindowsServer2025Lab@ebigpictures.com/" rel="noopener">Book a lab slot</a></li>
      <li><a href="https://access.ebigpictures.com/">Lab access (team sign-in)</a></li>
      <li><a href="https://ai.ebigpictures.com/">AI Labs: Copilot Studio and Cowork</a></li>
      <li><a href="{REPO_URL['hyb']}" rel="noopener">Hybrid labs on GitHub</a></li>
      <li><a href="{REPO_URL['sec']}" rel="noopener">Security labs on GitHub</a></li>
    </ul>
  </div>
  <p class="fine">Lab environments only: several labs change security settings, lock accounts or force recovery. Never run them on production systems. An independent site, not affiliated with Microsoft. © 2026 Mohamed Dyabi</p>
</footer>
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
    hyb_items = [(re.sub(r"^Lab \d+:\s*", "", l), t) for l, t in hyb_nav[1:-1]]
    hyb_list = "".join(f'<li><a href="{t}">{html.escape(l)}</a></li>' for l, t in hyb_items)
    sec_items = [(re.sub(r"^Chapter \d+:\s*", "", ti), c, len(it)) for ti, c, it in sec_groups]
    sec_list = "".join(f'<li><a href="{c}">{html.escape(ti)}</a> <span class="count">{n} labs</span></li>'
                       for ti, c, n in sec_items)
    body = f"""
<section class="hero">
  <div class="wrap">
    <p class="kicker">Windows Server 2025 · Azure Arc · Security</p>
    <h1>Learn Windows Server by doing it</h1>
    <p class="lede">Two hands-on tracks. In the first, you take an on-premises server and manage it from Azure. In the second, you watch an attack, build the control that stops it, and prove that it works.</p>
    <p class="cta"><a class="btn primary" href="hybrid/index.html">Start the hybrid track</a><a class="btn" href="security/setup.html">Build the security lab</a></p>
  </div>
</section>

<div class="wrap">
<h2 class="section-title">Browse the tracks</h2>
<div class="cards">
  <article class="card">
    <div class="card-head"><span class="ico c-blue">{ICONS['hybrid']}</span><div><p class="card-kicker">Learning path · {n_hyb} labs · about 8 hours</p>
    <h3><a href="hybrid/index.html">Hybrid management with Azure Arc</a></h3></div></div>
    <p>One Windows Server 2025 VM per person. Connect it to Azure Arc, unlock the Software Assurance benefits, and use Hotpatch, Azure Policy, Azure Monitor, Change Tracking, Defender for Cloud and Windows Admin Center in Azure. Every lab ends with customer talking points.</p>
    <ol class="mini">{hyb_list}</ol>
    <p class="card-foot"><a href="hybrid/index.html">Start the hybrid track ›</a></p>
  </article>
  <article class="card">
    <div class="card-head"><span class="ico c-red">{ICONS['security']}</span><div><p class="card-kicker">Learning path · {n_sec} labs · attack, then defend</p>
    <h3><a href="security/index.html">Securing Windows Server</a></h3></div></div>
    <p>Four VMs, one domain, and an attacker. Each lab shows the attack first, then builds the control that stops it: passwords and lockout, Credential Guard, App Control, Protected Users, RODC, delegation, Sentinel, IPsec and BitLocker.</p>
    <ol class="mini">{sec_list}</ol>
    <p class="card-foot"><a href="security/setup.html">Build the lab and start ›</a></p>
  </article>
</div>

<section class="band">
  <span class="ico c-green">{ICONS['access']}</span>
  <div>
    <p class="card-kicker">MTS team · Remote lab access</p>
    <h2>Book a lab slot and connect from anywhere</h2>
    <p>Book a 2-hour slot (Wednesday to Friday, 10:00 to 20:00, Morocco time) on your own Windows Server 2025 VM, reached over HTTPS through our Remote Desktop Gateway. You get your sign-in details before the slot, then download your connection file and start the hybrid labs.</p>
  </div>
  <div class="band-actions"><a class="btn primary" href="https://bookings.cloud.microsoft/book/WindowsServer2025Lab@ebigpictures.com/" target="_blank" rel="noopener">Book a lab slot</a><a class="btn" href="https://access.ebigpictures.com/">Sign in to get your file</a></div>
</section>

<section class="band">
  <span class="ico c-purple">{ICONS['ai']}</span>
  <div>
    <p class="card-kicker">New · AI Labs</p>
    <h2>Copilot Studio and Copilot Cowork labs</h2>
    <p>Build AI agents step by step: from a simple Agent Builder agent to Copilot Studio agents with tools, workflows, human approval and connected agents. Plus a hands-on Copilot Cowork workshop.</p>
  </div>
  <div class="band-actions"><a class="btn primary" href="https://ai.ebigpictures.com/copilot-studio/index.html">Copilot Studio labs</a><a class="btn" href="https://ai.ebigpictures.com/cowork/index.html">Copilot Cowork labs</a></div>
</section>

<h2 class="section-title">How every lab works</h2>
<ol class="steps5">
  <li><strong>The situation</strong><span>A customer question or an attacker's move: why this lab matters.</span></li>
  <li><strong>The concepts</strong><span>Just enough theory, in plain words, with an analogy.</span></li>
  <li><strong>Step by step</strong><span>Build it on your own VM, with the exact commands.</span></li>
  <li><strong>Prove it</strong><span>A verification command or a portal view that shows it works.</span></li>
  <li><strong>Takeaway</strong><span>Talking points for the customer, or the one idea to remember.</span></li>
</ol>

<h2 class="section-title">What you need</h2>
<div class="cards two">
  <div class="card plain"><h3>Hybrid track</h3><p>A Windows Server 2025 VM (your instructor provides one), an Azure subscription where you can create a resource group, and about two days.</p></div>
  <div class="card plain"><h3>Security track</h3><p>A Hyper-V host for four Generation 2 VMs with Secure Boot and a virtual TPM, plus Azure and Microsoft 365 trials for the cloud chapters.</p></div>
</div>
</div>
"""
    return shell("index.html", "Windows Server Labs", body)


# --------------------------------------------------------------------------
# 5b. Lab access page (RD Gateway connection files for the MTS team)
# --------------------------------------------------------------------------
GATEWAY = "labs.ebigpictures.com"
ENGINEERS = [(f"mts{i:02d}", f"WS25-VM{i:02d}", f"192.168.100.{89 + i}") for i in range(1, 9)]


def rdp_text(user, ip):
    return "\r\n".join([
        f"full address:s:{ip}", f"username:s:.\\{user}", f"gatewayhostname:s:{GATEWAY}",
        "gatewayusagemethod:i:1", "gatewayprofileusagemethod:i:1", "gatewaycredentialssource:i:0",
        "promptcredentialonce:i:0", "authentication level:i:2", "prompt for credentials:i:1",
        "screen mode id:i:2", "use multimon:i:0", "redirectclipboard:i:1", "redirectprinters:i:0",
        "redirectdrives:i:0", "audiomode:i:2", ""])


def access_page():
    out = "access/index.html"
    rows = "".join(
        f'<tr><td><code>{u}</code></td><td>{vm}</td><td><code>{ip}</code></td>'
        f'<td><a class="btn primary small" href="rdp/{u}-{vm}.rdp" download>Download {u}.rdp</a></td></tr>'
        for u, vm, ip in ENGINEERS)
    labs = "".join(f'<li><a href="{rel(out, t)}">{html.escape(re.sub(r"^Lab \d+:\s*", "", l))}</a></li>'
                   for l, t in hyb_nav[1:-1])
    body = f"""
<p class="eyebrow">MTS team · Windows Server 2025 · Azure Arc</p>
<h1>Hybrid lab access</h1>
<p class="lede">Each engineer has a personal Windows Server 2025 VM for the hybrid labs. You reach it from anywhere over HTTPS, through our Remote Desktop Gateway at <code>{GATEWAY}</code>. Your password arrives privately from Mohamed, never on this page.</p>

<h2>Connect in four steps</h2>
<ol>
<li>Find your user name in the table below and download your connection file.</li>
<li>Double-click the <code>.rdp</code> file. On a Mac, iPad or phone, open it with Microsoft's free <strong>Windows App</strong>.</li>
<li>At the security warning, tick <strong>Clipboard</strong> if you want copy-paste, then click <strong>Connect</strong>.</li>
<li>Sign in twice, with the same password both times: first the gateway as <code>RDGW01\\mtsNN</code>, then your lab VM as <code>.\\mtsNN</code>. For example <code>RDGW01\\mts03</code>, then <code>.\\mts03</code>.</li>
</ol>

<h2>Your connection file</h2>
<p>Each user name reaches one VM only. Download only your own file.</p>
<div class="table-wrap"><table class="access-table">
<thead><tr><th>User</th><th>Lab VM</th><th>Address</th><th>Connection file</th></tr></thead>
<tbody>{rows}</tbody>
</table></div>

<h2>About the security warning</h2>
<div class="alert note"><p class="alert-title">Note</p><p><strong>"Unknown publisher" is expected.</strong> It appears because the connection file isn't digitally signed. The connection itself is encrypted over HTTPS to <code>{GATEWAY}</code> with a trusted certificate. Check that the gateway server shown is <code>{GATEWAY}</code>, then click Connect.</p></div>

<h2>The labs</h2>
<p>Nine labs, about 8 hours in total. Do them in order. Each ends with customer talking points.</p>
<ol>{labs}</ol>

<h2>If something goes wrong</h2>
<dl class="faq">
<dt>"There was a problem connecting to the remote resource"</dt><dd>Check that you typed the gateway sign-in as <code>RDGW01\\mtsNN</code>. If you're on the same office network as the lab, try from another connection, such as a phone hotspot.</dd>
<dt>Your account is locked</dt><dd>After Lab 9 (security baseline), three wrong passwords lock your VM account for 15 minutes. Wait, then sign in carefully.</dd>
<dt>You broke your VM during a lab</dt><dd>That's fine. Ask Mohamed: a VM is reset to its clean baseline in a few minutes.</dd>
<dt>Something else</dt><dd>Send Mohamed the error message, or a screenshot of it, and the time it happened.</dd>
</dl>
<p><em>Don't forward your password outside the team.</em></p>
"""
    return shell(out, "Hybrid lab access", body, "access", kind="Team guide",
                 head='<meta name="robots" content="noindex, nofollow">\n')

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
        kind = ("Lab" if ("/lab-" in src or (repo == "hyb" and src.startswith("labs/") and "cleanup" not in src))
                else "Chapter" if src.endswith("README.md") and src.startswith("labs/") else "Article")
        fh.write(shell(out, titles[(repo, src)], body, track, extra, kind=kind))

with open(os.path.join(OUT, "index.html"), "w", encoding="utf-8") as fh:
    fh.write(home_page())

# The lab access page lives in the private repo medyabi/mts-lab-access
# (Azure Static Web Apps, sign-in + invitation), at https://access.ebigpictures.com

TOOLS = os.path.dirname(os.path.abspath(__file__))
shutil.copyfile(os.path.join(TOOLS, "site.css"), os.path.join(OUT, "assets", "site.css"))
shutil.copyfile(os.path.join(TOOLS, "favicon.svg"), os.path.join(OUT, "assets", "favicon.svg"))
import subprocess
from PIL import Image
for size, name in ((32, "favicon-32.png"), (180, "apple-touch-icon.png"), (48, "_ico48.png")):
    subprocess.run(["rsvg-convert", "-w", str(size), "-h", str(size),
                    os.path.join(TOOLS, "favicon.svg"), "-o", os.path.join(OUT, "assets", name)], check=True)
Image.open(os.path.join(OUT, "assets", "_ico48.png")).save(os.path.join(OUT, "favicon.ico"), sizes=[(16, 16), (32, 32), (48, 48)])
os.remove(os.path.join(OUT, "assets", "_ico48.png"))
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
