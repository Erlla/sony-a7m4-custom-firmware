from pathlib import Path
import importlib.util
import random
import sys
import unittest
APP=Path(__file__).resolve().parents[1]/'app'
sys.path.insert(0,str(APP))
spec=importlib.util.spec_from_file_location('counter',APP/'receiver_stock/byte_diff.py')
counter=importlib.util.module_from_spec(spec);spec.loader.exec_module(counter)


class ByteDiffTests(unittest.TestCase):
    def check(self,a,b):
        self.assertEqual(counter.count_differences(a,b),sum(x != y for x,y in zip(a,b)))

    def test_all_values_and_cross_byte_edges(self):
        a=bytes(range(256))
        for n in range(256): self.check(a,bytes([n])*256)
        for bit in range(8): self.check(bytes(101),bytes([1 << bit,0])*50+b'\x00')

    def test_random_block_boundaries_and_mutable_input(self):
        rng=random.Random(20261110)
        for n in (0,1,7,65535,65536,65537,131073):
            a=rng.randbytes(n);b=bytearray(a)
            for i in range(0,n,17): b[i]^=255
            self.check(a,b)
            self.check(a,rng.randbytes(n))

    def test_identical_and_all_different(self):
        self.check(bytes(131100),bytes(131100))
        self.check(bytes(131100),b'\xff'*131100)

    def test_invalid_types_and_lengths(self):
        with self.assertRaises(TypeError): counter.count_differences('a',b'a')
        with self.assertRaises(ValueError): counter.count_differences(b'a',b'')

    def test_both_lineages_use_same_counter(self):
        self.assertEqual((APP/'receiver_stock/byte_diff.py').read_bytes(),(APP/'receiver_custom/byte_diff.py').read_bytes())

if __name__ == '__main__': unittest.main()
