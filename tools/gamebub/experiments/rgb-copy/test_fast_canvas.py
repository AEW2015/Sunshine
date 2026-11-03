import unittest
from PIL import Image
import av
from host import canvas
from fast_canvas import fast_canvas
from msv1 import encode_receiver_jpeg


class Equivalence(unittest.TestCase):
    def test_modes_shapes_and_ownership(self):
        for mode in ('RGB','RGBA','L','P'):
            for size in ((1920,1080),(405,720),(720,405),(1,1)):
                with self.subTest(mode=mode,size=size):
                    img=Image.new(mode,size)
                    before=img.tobytes()
                    for filt in (Image.Resampling.BILINEAR,Image.Resampling.BOX):
                        a,b=canvas(img,filt),fast_canvas(img,filt)
                        self.assertEqual((a.mode,a.size,a.tobytes()),(b.mode,b.size,b.tobytes()))
                        self.assertEqual(bytes(encode_receiver_jpeg(a,65)),bytes(encode_receiver_jpeg(b,65)))
                        self.assertIsNot(a,img); self.assertIsNot(b,img)
                    self.assertEqual(img.tobytes(),before)

    def test_output_is_owned_after_source_changes(self):
        img=Image.new('RGB',(1280,720),(10,20,30))
        result=fast_canvas(img,Image.Resampling.BILINEAR)
        old=result.tobytes();img.paste((255,0,0),(0,0,1280,720))
        self.assertEqual(result.tobytes(),old)

    def test_video_frame_delegates_to_stock_path(self):
        video=av.VideoFrame.from_image(Image.new('RGB',(160,90),(50,80,120)))
        self.assertEqual(fast_canvas(video).tobytes(),canvas(video).tobytes())


if __name__=='__main__': unittest.main()
