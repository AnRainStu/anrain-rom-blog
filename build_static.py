"""Build a portable static backup from seed.py; it never reads the live database."""
import os
import posixpath
import re
import shutil
import sys
import tempfile
from pathlib import Path
from urllib.parse import parse_qs, urlsplit

BASE = Path(__file__).resolve().parent
DEST = Path(sys.argv[1]).resolve() if len(sys.argv) > 1 else BASE / 'site'

with tempfile.TemporaryDirectory(prefix='anrain-static-') as temp:
    os.environ['ANRAIN_DATA_DIR'] = temp
    from app import app, db

    with app.app_context():
        ids = [row['id'] for row in db().execute('SELECT id FROM posts ORDER BY id')]

    pages = {'/': 'index.html', '/?device=oneplus-13t': 'device/index.html'}
    pages.update({f'/?category={name}': f'category/{name}/index.html' for name in ('native', 'official', 'port')})
    pages.update({f'/post/{post_id}': f'post/{post_id}/index.html' for post_id in ids})

    def rewrite_url(url, output):
        parsed = urlsplit(url)
        if parsed.scheme or parsed.netloc or not parsed.path.startswith('/'):
            return url
        target = None
        if parsed.path.startswith('/static/'):
            target = parsed.path.lstrip('/')
        elif parsed.path == '/':
            params = parse_qs(parsed.query)
            if params.get('category', [''])[0] in ('native', 'official', 'port'):
                target = 'category/' + params['category'][0] + '/index.html'
            elif params.get('device', [''])[0] == 'oneplus-13t':
                target = 'device/index.html'
            else:
                target = 'index.html'
        elif re.fullmatch(r'/post/\d+', parsed.path):
            target = parsed.path.lstrip('/') + '/index.html'
        if target is None:
            return url
        relative = posixpath.relpath(target, posixpath.dirname(output) or '.')
        return relative + ('#' + parsed.fragment if parsed.fragment else '')

    client = app.test_client()
    for route, output in pages.items():
        response = client.get(route)
        if response.status_code != 200:
            raise RuntimeError(f'{route}: HTTP {response.status_code}')
        html = response.get_data(as_text=True)
        html = re.sub(r'((?:href|src)=")([^"]+)(")', lambda m: m[1] + rewrite_url(m[2].replace('&amp;', '&'), output).replace('&', '&amp;') + m[3], html)
        html = re.sub(r'<form class="filter-row".*?</form>', '<div class="static-backup-note">这是 GitHub 静态备用页，内容来自仓库中的发布记录。</div>', html, flags=re.DOTALL)
        html = html.replace('<main class="wrap">', '<main class="wrap"><div class="static-backup-note">备用下载站 · 静态快照；更新以站长发布为准。</div>', 1)
        html = html.replace('</head>', '<style>.static-backup-note{margin:12px 0;color:#dcc4e8;font-size:12px}</style></head>', 1)
        path = DEST / output
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(html, encoding='utf-8')
    shutil.copytree(BASE / 'static', DEST / 'static', dirs_exist_ok=True)
    print(f'Built {len(pages)} static pages in {DEST}')
