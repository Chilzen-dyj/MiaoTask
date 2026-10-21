import threading
import unittest
from http.server import ThreadingHTTPServer
from urllib.error import HTTPError
from urllib.request import urlopen

from PIL import Image

from backend.core.service.branding import ICON_SIZES, windows_icon_path
from backend.core.service.panel import make_handler
from scripts.check_public_files import audit_file


class BrandingTests(unittest.TestCase):
    def test_exports_keep_alpha_and_all_platform_sizes(self):
        folder = windows_icon_path().parent
        for size in ICON_SIZES:
            with Image.open(folder / f'miaotask-{size}.png') as icon:
                self.assertEqual(icon.size, (size, size))
                self.assertEqual(icon.mode, 'RGBA')
                self.assertEqual(icon.getextrema()[3], (0, 255))
        with Image.open(windows_icon_path()) as icon:
            self.assertEqual(icon.ico.sizes(), {(s, s) for s in (16, 20, 24, 32, 40, 48, 64, 128, 256)})

    def test_public_audit_only_allows_reviewed_icon_names(self):
        ico = windows_icon_path().read_bytes()
        self.assertEqual(audit_file('frontend/assets/miaotask.ico', ico), [])
        self.assertTrue(audit_file('frontend/assets/private-device.ico', ico))
        self.assertTrue(audit_file('frontend/assets/miaotask.ico', b'not an icon'))
        for size in ICON_SIZES:
            name = f'miaotask-{size}.png'
            self.assertEqual(audit_file(f'frontend/assets/{name}', (windows_icon_path().parent / name).read_bytes()), [])

    def test_http_exposes_icons_but_not_master_or_other_local_files(self):
        server = ThreadingHTTPServer(('127.0.0.1', 0), make_handler(None, 'test-only'))
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        base = f'http://127.0.0.1:{server.server_port}'
        try:
            for path, mime, signature in (
                ('/assets/miaotask-32.png', 'image/png', b'\x89PNG\r\n\x1a\n'),
                ('/assets/miaotask.ico', 'image/x-icon', b'\0\0\1\0'),
                ('/favicon.ico', 'image/x-icon', b'\0\0\1\0'),
            ):
                with urlopen(base + path, timeout=3) as response:
                    self.assertEqual(response.headers.get_content_type(), mime)
                    self.assertTrue(response.read().startswith(signature))
            for path in ('/assets/miaotask-master.png', '/assets/../version.json', '/assets/private.png'):
                with self.assertRaises(HTTPError) as error:
                    urlopen(base + path, timeout=3)
                self.assertEqual(error.exception.code, 404)
        finally:
            server.shutdown()
            server.server_close()
            thread.join(timeout=3)


if __name__ == '__main__':
    unittest.main()
