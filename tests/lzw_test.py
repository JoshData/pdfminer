#!/usr/bin/env python2
""" Unit tests for ASCII85/ASCIIHex decoder (Adobe version).

"""

import unittest

from pdfminer.lzw import lzwdecode


class TestLZW(unittest.TestCase):

    decoded = '\x2d\x2d\x2d\x2d\x2d\x41\x2d\x2d\x2d\x42'

    def test_lzwdecode(self):
        """Test LZW decoder"""
        self.assertEqual(self.decoded, lzwdecode('\x80\x0b\x60\x50\x22\x0c\x0c\x85\x01'))

    def test_lzwdecode_corrupt(self):
        """Test lzwdecode gracefully ignores corrupt data"""
        self.assertEqual(self.decoded, lzwdecode('\x80\x0b\x60\x50\x22\x0c\x0c\x85\x01\xff\xff'))
        self.assertEqual('', lzwdecode('\x80\x80\r\n'))


if __name__ == '__main__':
    unittest.main()
