import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
from build_site import versioned_html


class DeploymentCacheTests(unittest.TestCase):
    def test_new_data_refreshes_its_url_and_unchanged_code_keeps_its_url(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            names = ('styles.css', 'data.js', 'app.js', 'food-art.js', 'search.js')
            for filename in names:
                (root/filename).write_text('first', encoding='utf-8')
            html = ''.join(f'<script src="{name}"></script>' for name in names)
            before = versioned_html(html, root)
            (root/'data.js').write_text('second', encoding='utf-8')
            after = versioned_html(html, root)
            self.assertNotEqual(before.split('data.js?v=')[1][:12], after.split('data.js?v=')[1][:12])
            self.assertEqual(before.split('app.js?v=')[1][:12], after.split('app.js?v=')[1][:12])
            self.assertNotIn('src="data.js"', after)


if __name__ == '__main__':
    unittest.main()
