"""Isolated prototype: avoid copying input already in Pillow RGB mode."""
from PIL import Image
import av
from host import WIDTH, HEIGHT, CONTENT_HEIGHT, canvas


def fast_canvas(image, resampling=Image.Resampling.LANCZOS):
    """Return a new letterboxed canvas; preserve the stock video-frame path."""
    if isinstance(image, av.VideoFrame):
        return canvas(image, resampling)
    scale = min(WIDTH / image.width, CONTENT_HEIGHT / image.height)
    size = (max(1, round(image.width * scale)), max(1, round(image.height * scale)))
    source = image if image.mode == 'RGB' else image.convert('RGB')
    resized = source.resize(size, resampling)
    result = Image.new('RGB', (WIDTH, HEIGHT))
    result.paste(resized, ((WIDTH - size[0]) // 2, (HEIGHT - size[1]) // 2))
    return result
