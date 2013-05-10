#!/usr/bin/env python2
""" Unit tests for pdf2txt command line utility.

Perform pdf2txt on every pdf in the samples directory and compare the output with the relevant ref file.

"""

import os
import unittest

from pdfminer import pdf2txt


SAMPLES_PATH = os.path.join(os.path.dirname(__file__), '..', 'samples')


class TestPdf2Txt(unittest.TestCase):
    pass


def test_generator(path, fmt):
    def test(self):
        outpath = '%s.%s' % (os.path.splitext(path)[0], fmt)
        refpath = '%s.ref' % outpath
        pdf2txt.main([path, '-p', '1', '-V', '-o', outpath])
        with open(outpath, 'r') as outf:
            with open(refpath, 'r') as reff:
                self.assertEqual(reff.read(), outf.read())
    test.__doc__ = 'Test %s conversion to %s' % (os.path.basename(path), fmt)
    return test


def generate_all_tests():
    """Find all PDFs in the samples directory and generate tests for them"""
    paths = []
    for root, dirs, files in os.walk(SAMPLES_PATH):
        for fn in files:
            if fn.endswith('.pdf'):
                paths.append(os.path.join(SAMPLES_PATH, root, fn))
    for path in paths:
        name = os.path.splitext(os.path.basename(path))[0]
        for fmt in ['txt', 'html', 'xml']:
            test_name = 'test_%s_%s' % (name, fmt)
            test = test_generator(path, fmt)
            setattr(TestPdf2Txt, test_name, test)


generate_all_tests()


if __name__ == '__main__':
    unittest.main()
