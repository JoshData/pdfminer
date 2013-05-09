#!/usr/bin/env python2
""" Unit tests for Rijndael encryption algorithm.

"""

import unittest

from pdfminer.rijndael import RijndaelDecryptor, RijndaelEncryptor


class TestRijndael(unittest.TestCase):

    key = '00010203050607080a0b0c0d0f101112'.decode('hex')
    plaintext = '506812a45f08c889b97f5980038b8359'.decode('hex')
    ciphertext = 'd8f532538289ef7d06b506a4fd5be9c9'.decode('hex')

    def test_rijndael_decryptor(self):
        """Test Rijndael decryptor"""
        self.assertEqual(self.plaintext, RijndaelDecryptor(self.key, 128).decrypt(self.ciphertext))

    def test_rijndael_encryptor(self):
        """Test Rijndael encryptor"""
        self.assertEqual(self.ciphertext, RijndaelEncryptor(self.key, 128).encrypt(self.plaintext))


if __name__ == '__main__':
    unittest.main()
