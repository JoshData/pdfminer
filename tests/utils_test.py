#!/usr/bin/env python2
""" Unit tests for utils.

"""

import unittest

from pdfminer.utils import nunpack


class TestUtils(unittest.TestCase):

    def test_nunpack(self):
        """Test unpacking of 1 to 4 byte integers (big endian)"""
        self.assertEqual(0x26, nunpack('\x26'))
        self.assertEqual(0xa51f33, nunpack('\xa5\x1f\x33'))
        self.assertEqual(0x1151bb3e, nunpack('\x11\x51\xbb\x3e'))
        self.assertEqual(1234, nunpack('', default=1234))
        with self.assertRaises(TypeError):
            nunpack('\xa5\x1f\x33\x11\x51\xbb\x3e')


if __name__ == '__main__':
    unittest.main()
