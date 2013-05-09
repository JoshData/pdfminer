#!/usr/bin/env python2
""" Unit tests for Arcfour encryption algorithm.

"""

import unittest

from pdfminer.arcfour import Arcfour


class TestArcfour(unittest.TestCase):

    def test_arcfour(self):
        """Test arcfour encryption algorithm"""
        self.assertEqual('bbf316e8d940af0ad3', Arcfour('Key').process('Plaintext').encode('hex'))
        self.assertEqual('1021bf0420', Arcfour('Wiki').process('pedia').encode('hex'))
        self.assertEqual('45a01f645fc35b383552544b9bf5', Arcfour('Secret').process('Attack at dawn').encode('hex'))


if __name__ == '__main__':
    unittest.main()
