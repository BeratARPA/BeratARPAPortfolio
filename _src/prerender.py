"""Sayfanın içeriğini HTML'in içine gömer.

Site data.json'dan JavaScript ile çizilir. JavaScript çalıştırmayan arama motorları ve
yapay zekâ tarayıcıları bu yüzden boş bir sayfa görür. Bu betik kaynak şablonu
(_src/index.html) yerel bir sunucuda Edge ile çalıştırır, çizilmiş başlığı, gövdeyi,
alt bilgiyi ve yapılandırılmış veriyi şablona yerleştirip kökteki index.html'i yazar.
Tarayıcıda JavaScript yine her şeyi canlı veriyle yeniden çizer.

Kullanım (depo kökünden):
    python _src/prerender.py          # index.html'i üretir
    python _src/prerender.py --og     # ayrıca paylaşım kartını (og-card.png) yeniden çeker

Kural: sayfada değişiklik _src/index.html'de yapılır, sonra bu betik çalıştırılır.
Kökteki index.html elle düzenlenmez; her çalıştırmada yeniden yazılır.
"""
import functools
import http.server
import re
import shutil
import subprocess
import sys
import tempfile
import threading
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SRC = ROOT / "_src" / "index.html"
OUT = ROOT / "index.html"
EDGE = Path(r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe")


class Quiet(http.server.SimpleHTTPRequestHandler):
    def end_headers(self):
        self.send_header("Cache-Control", "no-store")
        super().end_headers()

    def log_message(self, *args):
        pass


def serve():
    handler = functools.partial(Quiet, directory=str(ROOT))
    srv = http.server.ThreadingHTTPServer(("127.0.0.1", 0), handler)
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    return srv, srv.server_address[1]


def edge(args, profile):
    return subprocess.run([str(EDGE), "--headless=new", "--disable-gpu", "--no-first-run",
                           "--hide-scrollbars", f"--user-data-dir={profile}", *args],
                          capture_output=True, timeout=120)


def block(html, pattern, name):
    m = re.search(pattern, html, re.S)
    if not m:
        sys.exit(f"{name} bulunamadı; çizim tamamlanmamış olabilir.")
    return m


def main():
    sys.stdout.reconfigure(encoding="utf-8")
    template = SRC.read_text(encoding="utf-8")
    # sunucu şablonu kökten sunsun: göreli yollar (data.json, Resources/…) aynı kalır
    OUT.write_text(template, encoding="utf-8", newline="\n")
    srv, port = serve()
    profile = tempfile.mkdtemp(prefix="prerender-")
    try:
        # geniş masaüstü penceresi: zaman haritası yatay çizilir, telefonda JavaScript dikeye çevirir
        run = edge(["--window-size=1440,900", "--virtual-time-budget=12000",
                    "--dump-dom", f"http://127.0.0.1:{port}/?lang=tr"], profile)
        dom = run.stdout.decode("utf-8", "replace")
        header = block(dom, r'<header class="top" id="top">.*?</header>', "header").group(0)
        body = block(dom, r'<main id="main">.*</main>', "main").group(0)
        footer = block(dom, r"<footer>.*?</footer>", "footer").group(0)
        ld = block(dom, r'<script type="application/ld\+json" id="ldjson">(.*?)</script>', "ld+json").group(1)
        h1 = block(body, r'<h1 id="h1">(.*?)</h1>', "h1").group(1).strip()
        if not h1 or len(ld) < 100:
            sys.exit("İçerik boş geldi; veri yüklenmemiş olabilir. index.html şablon olarak kaldı.")

        page = template
        page = re.sub(r'<header class="top" id="top">.*?</header>', lambda _: header, page, count=1, flags=re.S)
        page = re.sub(r'<main id="main">.*</main>', lambda _: body, page, count=1, flags=re.S)
        page = re.sub(r"<footer>.*?</footer>", lambda _: footer, page, count=1, flags=re.S)
        page = re.sub(r'(<script type="application/ld\+json" id="ldjson">).*?(</script>)',
                      lambda m: m.group(1) + ld + m.group(2), page, count=1, flags=re.S)
        OUT.write_text(page, encoding="utf-8", newline="\n")
        print(f"index.html yazıldı: {len(page):,} bayt, başlık: {h1}")

        if "--og" in sys.argv:
            card = ROOT / "Resources" / "Images" / "og-card.png"
            edge(["--window-size=1200,630", "--virtual-time-budget=12000",
                  f"--screenshot={card}", f"http://127.0.0.1:{port}/_src/og-card.html"], profile)
            print(f"paylaşım kartı: {card.stat().st_size:,} bayt")
    finally:
        srv.shutdown()
        shutil.rmtree(profile, ignore_errors=True)


if __name__ == "__main__":
    main()
