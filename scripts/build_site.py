"""Create the safe static deployment directory. API keys must never be copied."""
from pathlib import Path
import shutil
import hashlib
ROOT=Path(__file__).resolve().parents[1]
DST=ROOT/'site'


def versioned_html(html, directory):
    # A new HTML page must not execute a previously cached app/data bundle.
    # Content hashes also refresh data.js after every successful daily update.
    for filename in ('styles.css', 'data.js', 'app.js', 'food-art.js', 'search.js'):
        digest = hashlib.sha256((directory/filename).read_bytes()).hexdigest()[:12]
        html = html.replace(f'"{filename}"', f'"{filename}?v={digest}"')
    return html


def main():
    DST.mkdir(exist_ok=True)
    for filename in ('index.html','styles.css','data.js','app.js','food-art.js','search.js','favicon.svg'):
        shutil.copy2(ROOT/filename,DST/filename)
    html = (ROOT/'index.html').read_text(encoding='utf-8')
    (DST/'index.html').write_text(versioned_html(html, ROOT), encoding='utf-8')
    (DST/'.nojekyll').write_text('',encoding='utf-8')
    print('Site built at',DST)


if __name__ == '__main__':
    main()
