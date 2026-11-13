"""Target import regressions that can silently pair the wrong colour values."""
from pathlib import Path
import sys
import tempfile
import unittest

import numpy as np
from PIL import ImageCms
import tifffile

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'source'))
from chart_target import load_tiff
from evaluation import chart_qualification


class ChartTargetTests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        self.path = Path(self.directory.name) / 'target.tif'
        self.dataset = dict(height=64, width=96, tile=32, columns=3, rows=2,
                            samples=6, sampling='centre five', dataset_id='test')
        self.pixels = np.zeros((64, 96, 3), dtype=np.uint16)
        self.expected = np.arange(18, dtype=np.uint16).reshape(6, 3) * 3000
        for index, colour in enumerate(self.expected):
            y, x = index // 3 * 32 + 16, index % 3 * 32
            self.pixels[y, x + 14:x + 19] = colour
        self.profile = ImageCms.ImageCmsProfile(ImageCms.createProfile('sRGB')).tobytes()

    def write(self, *, pixels=None, profile=True, orientation=None, compression=None):
        tags = [(34675, 'B', len(self.profile), self.profile, False)] if profile else []
        if orientation is not None:
            tags.append((274, 'H', 1, orientation, False))
        tifffile.imwrite(self.path, self.pixels if pixels is None else pixels,
                         photometric='rgb', metadata=None, extratags=tags,
                         compression=compression)

    def test_row_order_and_rgb16_precision_in_plain_zip_and_lzw_exports(self):
        for compression in (None, 'deflate', 'lzw'):
            with self.subTest(compression=compression):
                self.write(compression=compression)
                actual, info = load_tiff(self.path, self.dataset)
                np.testing.assert_array_equal(actual, self.expected.astype(float) / 65535)
                self.assertFalse(info['assumed_srgb'])

    def test_missing_profile_requires_explicit_confirmation(self):
        self.write(profile=False)
        with self.assertRaisesRegex(ValueError, 'no ICC'):
            load_tiff(self.path, self.dataset)
        actual, info = load_tiff(self.path, self.dataset, assume_srgb=True)
        self.assertTrue(info['assumed_srgb'])
        np.testing.assert_array_equal(actual, self.expected.astype(float) / 65535)

    def test_wrong_size_bit_depth_and_orientation(self):
        for options, message in ((dict(pixels=self.pixels[:32]), 'dimensions'),
                                 (dict(pixels=self.pixels.astype(np.uint8)), '16-bit'),
                                 (dict(orientation=6), 'orientation')):
            with self.subTest(options=list(options)):
                self.write(**options)
                with self.assertRaisesRegex(ValueError, message):
                    load_tiff(self.path, self.dataset)

    def test_explicit_assumption_does_not_relabel_a_different_profile(self):
        self.profile = ImageCms.ImageCmsProfile(ImageCms.createProfile('LAB')).tobytes()
        self.write()
        with self.assertRaisesRegex(ValueError, 'Convert to sRGB'):
            load_tiff(self.path, self.dataset, assume_srgb=True)

    def test_aggregate_reports_a_local_tradeoff(self):
        baseline = np.array([1., 2., 3., 4., 5.])
        candidate = np.array([1.1, 1., 2., 3., 4.])
        strict = chart_qualification(candidate, baseline)
        aggregate = chart_qualification(candidate, baseline, 'aggregate')
        self.assertFalse(strict['chart_candidate_qualified'])
        self.assertTrue(aggregate['chart_candidate_qualified'])
        self.assertFalse(aggregate['per_colour_guard'])
        self.assertEqual(aggregate['regressed_colour_count'], 1)
        self.assertAlmostEqual(aggregate['maximum_colour_regression'], .1)

    def test_aggregate_rejects_worse_tail_even_when_mean_improves(self):
        baseline = np.full(100, 2.)
        candidate = np.r_[np.zeros(90), np.full(10, 3.)]
        self.assertFalse(chart_qualification(candidate, baseline, 'aggregate')['chart_candidate_qualified'])


if __name__ == '__main__':
    unittest.main()
