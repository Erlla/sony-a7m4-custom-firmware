"""Read a user-exported RGB16 sRGB chart in the model's tile order."""
from io import BytesIO
from pathlib import Path

import numpy as np
from PIL import ImageCms
import tifffile
import support as w


def load_tiff(path, dataset, *, assume_srgb=False):
    path = Path(path)
    expected = (dataset['height'], dataset['width'], 3)
    with tifffile.TiffFile(path) as image:
        page = image.pages[0]
        if page.shape != expected:
            raise ValueError(f'Expected chart dimensions {expected}, got {page.shape}. '
                             'Export the original chart layout without resizing or cropping.')
        if page.dtype != np.dtype('uint16') or int(page.photometric) != 2:
            raise ValueError('Export a 16-bit RGB TIFF.')
        orientation = page.tags.get('Orientation')
        if orientation is not None and int(orientation.value) != 1:
            raise ValueError('Export the chart in its original top-left orientation.')
        profile = page.tags.get('InterColorProfile')
        description = None
        if profile is not None:
            description = ImageCms.getProfileDescription(
                ImageCms.ImageCmsProfile(BytesIO(profile.value))).strip()
            if not description.lower().startswith('srgb'):
                raise ValueError(f'Expected encoded sRGB, found ICC profile {description!r}. '
                                 'Convert to sRGB in the editor before exporting.')
        elif not assume_srgb:
            raise ValueError('TIFF has no ICC profile. Embed sRGB on export, or use '
                             '--assume-srgb if you have confirmed the export space.')
        software = page.tags.get('Software')
        software = str(software.value) if software is not None else None
        # Memory-map uncompressed exports; TIFF codecs handle ZIP/LZW exports.
        try:
            pixels = tifffile.memmap(path, page=0, mode='r')
        except ValueError:
            pixels = page.asarray()
        index = np.arange(dataset['samples'])
        y = index // dataset['columns'] * dataset['tile'] + 16
        x = index % dataset['columns'] * dataset['tile']
        samples = pixels[y[:, None], x[:, None] + np.arange(14, 19), :]
        target = samples.mean(axis=1, dtype=np.float64) / 65535.0
    metadata = dict(kind='custom-tiff', file=w.pin(path), shape=list(expected),
                    ICC_description=description, assumed_srgb=profile is None,
                    software=software, samples=len(target),
                    sampling=dataset['sampling'], dataset_id=dataset['dataset_id'])
    return target, metadata
