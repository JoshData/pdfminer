#!/usr/bin/env python2
""" Unit tests for psparser.py

"""

import logging
import unittest

from pdfminer.psparser import KWD, LIT, PSEOF, PSStackParser

logging.basicConfig()
logging.getLogger('pdfminer.psparser').setLevel(logging.DEBUG)
logging.getLogger('pdfminer.pdfparser').setLevel(logging.DEBUG)


class TestPSBaseParser(unittest.TestCase):

    TESTDATA = r'''%!PS
begin end
 "  @ #
/a/BCD /Some_Name /foo#5f#xbaa
0 +1 -2 .5 1.234
(abc) () (abc ( def ) ghi)
(def\040\0\0404ghi) (bach\\slask) (foo\nbaa)
(this % is not a comment.)
(foo
baa)
(foo\
baa)
<> <20> < 40 4020 >
<abcd00
12345>
func/a/b{(c)do*}def
[ 1 (z) ! ]
<< /foo (bar) >>
'''

    TOKENS = [
        (5, KWD('begin')), (11, KWD('end')), (16, KWD('"')), (19, KWD('@')),
        (21, KWD('#')), (23, LIT('a')), (25, LIT('BCD')), (30, LIT('Some_Name')),
        (41, LIT('foo_xbaa')), (54, 0), (56, 1), (59, -2), (62, 0.5),
        (65, 1.234), (71, 'abc'), (77, ''), (80, 'abc ( def ) ghi'),
        (98, 'def \x00 4ghi'), (118, 'bach\\slask'), (132, 'foo\nbaa'),
        (143, 'this % is not a comment.'), (170, 'foo\nbaa'), (180, 'foobaa'),
        (191, ''), (194, ' '), (199, '@@ '), (211, '\xab\xcd\x00\x124\x05'),
        (226, KWD('func')), (230, LIT('a')), (232, LIT('b')),
        (234, KWD('{')), (235, 'c'), (238, KWD('do*')), (241, KWD('}')),
        (242, KWD('def')), (246, KWD('[')), (248, 1), (250, 'z'), (254, KWD('!')),
        (256, KWD(']')), (258, KWD('<<')), (261, LIT('foo')), (266, 'bar'),
        (272, KWD('>>'))
    ]

    OBJS = [
        (23, LIT('a')), (25, LIT('BCD')), (30, LIT('Some_Name')),
        (41, LIT('foo_xbaa')), (54, 0), (56, 1), (59, -2), (62, 0.5),
        (65, 1.234), (71, 'abc'), (77, ''), (80, 'abc ( def ) ghi'),
        (98, 'def \x00 4ghi'), (118, 'bach\\slask'), (132, 'foo\nbaa'),
        (143, 'this % is not a comment.'), (170, 'foo\nbaa'), (180, 'foobaa'),
        (191, ''), (194, ' '), (199, '@@ '), (211, '\xab\xcd\x00\x124\x05'),
        (230, LIT('a')), (232, LIT('b')), (234, ['c']), (246, [1, 'z']),
        (258, {'foo': 'bar'}),
    ]

    def get_tokens(self, s):
        import io

        class MyParser(PSStackParser):
            def flush(self):
                self.add_results(*self.popall())

        parser = MyParser(io.StringIO(s))
        r = []
        try:
            while 1:
                r.append(parser.nexttoken())
        except PSEOF:
            pass
        return r

    def get_objects(self, s):
        import io

        class MyParser(PSStackParser):
            def flush(self):
                self.add_results(*self.popall())

        parser = MyParser(io.StringIO(s))
        r = []
        try:
            while 1:
                r.append(parser.nextobject())
        except PSEOF:
            pass
        return r

    def test_1(self):
        """Test PSBaseParser tokenization"""
        tokens = self.get_tokens(self.TESTDATA)
        #print tokens
        self.assertEqual(tokens, self.TOKENS)
        return

    def test_2(self):
        """Test PSStackParser object extraction"""
        objs = self.get_objects(self.TESTDATA)
        #print objs
        self.assertEqual(objs, self.OBJS)
        return


if __name__ == '__main__':
    unittest.main()
