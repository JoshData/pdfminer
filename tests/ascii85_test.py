#!/usr/bin/env python2
""" Unit tests for ASCII85/ASCIIHex decoder (Adobe version).

"""

import unittest

from pdfminer.ascii85 import ascii85decode, asciihexdecode


class TestAscii85(unittest.TestCase):

    def test_ascii85decode(self):
        """Test ASCII85 decoder"""
        self.assertEqual('Man is distinguished', ascii85decode('9jqo^BlbD-BleB1DJ+*+F(f,q'))
        self.assertEqual('pleasure.', ascii85decode('E,9)oF*2M7/c~>'))

    def test_asciihexdecode(self):
        """Test ASCIIHex decoder"""
        self.assertEqual('ab.cde', asciihexdecode('61 62 2e6364   65'))
        self.assertEqual('ab.cdep', asciihexdecode('61 62 2e6364   657>'))
        self.assertEqual('p', asciihexdecode('7>'))


if __name__ == '__main__':
    unittest.main()
