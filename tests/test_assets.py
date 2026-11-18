from pathlib import Path
import unittest

from PIL import Image

ASSETS=Path(__file__).resolve().parents[1]/'huarongdao'/'assets'

class AssetsTests(unittest.TestCase):
    def test_all_portraits_present_and_readable(self):
        for name in ('caocao','guanyu','zhangfei','zhaoyun','machao','huangzhong','soldier'):
            with self.subTest(name=name):
                path=ASSETS/'portraits'/f'{name}.png'
                self.assertTrue(path.is_file())
                with Image.open(path) as im:
                    im.verify()
                with Image.open(path) as im:
                    self.assertGreaterEqual(im.width, 250)
                    self.assertGreaterEqual(im.height, 250)

    def test_visual_textures_and_icon_present(self):
        for name in ('wood_board.jpg','wood_dark.jpg','parchment.jpg','icon.png','icon.ico'):
            with self.subTest(name=name):
                self.assertTrue((ASSETS/name).is_file())

if __name__=='__main__':
    unittest.main()
