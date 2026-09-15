"""Build the self-contained offline browser page from repository assets."""
from hashlib import sha256
from pathlib import Path
import json
import re
import subprocess
import sys

HERE = Path(__file__).resolve().parent

def main():
    subprocess.run([sys.executable, str(HERE / 'build_viewer.py')], check=True)
    fragment = (HERE / 'build/viewer-fragment.html').read_text()
    manifest = json.loads((HERE / 'browser_vendor/manifest.json').read_text())
    assets = {item['url']: item for item in manifest}
    for url in re.findall(r'<script\b[^>]*\bsrc="(https://[^"]+)"[^>]*></script>', fragment):
        item = assets[url]
        data = (HERE / item['file']).read_bytes()
        if sha256(data).hexdigest() != item['sha256']:
            raise ValueError('Bundled dependency hash mismatch: ' + item['file'])
        code = re.sub(r'</script', r'<\\/script', data.decode(), flags=re.I)
        pattern = r'<script\b[^>]*\bsrc="' + re.escape(url) + r'"[^>]*></script>'
        fragment = re.sub(pattern, lambda _: '<script>\n' + code + '\n</script>', fragment)
    assert not re.search(r'<script\b[^>]*\bsrc=', fragment)
    css = (HERE / 'assets/viewer.css').read_text()
    document = '\n'.join([
        '<!doctype html>', '<html lang="en">', '<head>',
        '<meta charset="utf-8">', '<meta name="viewport" content="width=device-width, initial-scale=1">',
        '<title>SWC Gromov–Wasserstein experiments</title>',
        '<style>' + css + '\nhtml>body{box-sizing:border-box;max-width:1280px;margin:0 auto;padding:24px} @media(max-width:530px){html>body{padding:12px}}</style>',
        '</head>', '<body>', fragment, '</body>', '</html>',
    ])
    (HERE / 'index.html').write_text(document)
    print(f"Offline page: {HERE / 'index.html'} ({len(document.encode()):,} bytes)")

if __name__ == '__main__':
    main()
