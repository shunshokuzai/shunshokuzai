"""Create the safe static deployment directory. API keys must never be copied."""
from pathlib import Path
import shutil
ROOT=Path(__file__).resolve().parents[1]
DST=ROOT/'site'
DST.mkdir(exist_ok=True)
for filename in ('index.html','styles.css','data.js','app.js','food-art.js','search.js','favicon.svg'):
    shutil.copy2(ROOT/filename,DST/filename)
(DST/'.nojekyll').write_text('',encoding='utf-8')
print('Site built at',DST)
