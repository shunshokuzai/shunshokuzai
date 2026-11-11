"""Create a single HTML file that works without extraction, internet or install."""
from pathlib import Path
root=Path(__file__).resolve().parents[1]
html=(root/'index.html').read_text(encoding='utf-8')
css=(root/'styles.css').read_text(encoding='utf-8')
data=(root/'data.js').read_text(encoding='utf-8')
app=(root/'app.js').read_text(encoding='utf-8')
art=(root/'food-art.js').read_text(encoding='utf-8')
search=(root/'search.js').read_text(encoding='utf-8')
html=html.replace('<link rel="stylesheet" href="styles.css">',f'<style>\n{css}\n</style>')
html=html.replace('<script src="data.js"></script><script src="food-art.js"></script><script src="search.js"></script><script src="app.js"></script>',f'<script>\n{data}\n</script><script>\n{art}\n</script><script>\n{search}\n</script><script>\n{app}\n</script>')
html=html.replace('<link rel="icon" href="favicon.svg" type="image/svg+xml">','')
(root/'旬食材まるわかり_プロトタイプ.html').write_text(html,encoding='utf-8')
print('Standalone created:',len(html.encode('utf-8')),'bytes')
