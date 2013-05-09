#!/usr/bin/env python2
""" Unit tests for RunLength decoder (Adobe version).

"""

import unittest

from pdfminer.runlength import rldecode


class TestRunLength(unittest.TestCase):

    def test_rldecode(self):
        """Test RunLength decoder"""
        self.assertEqual('1234567777777abcde', rldecode('\x05123456\xfa7\x04abcde\x80junk'))


if __name__ == '__main__':
    unittest.main()
