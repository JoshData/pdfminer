#!/usr/bin/env python2
"""
pdf2txt.py - convert pdf into text.

This script extracts text contents from a PDF file. It extracts all the text that are to be rendered programmatically,
i.e. text represented as ASCII or Unicode strings. It cannot recognize text drawn as images that would require optical
character recognition. It also extracts the corresponding locations, font names, font sizes, writing direction
(horizontal or vertical) for each text portion. You need to provide a password for protected PDF documents when its
access is restricted. You cannot extract any text from a PDF document which does not have extraction permission.

Note: Not all characters in a PDF can be safely converted to Unicode.

Examples

    $ pdf2txt.py -o output.html samples/naacl06-shinyama.pdf
    (extract text as an HTML file whose filename is output.html)

    $ pdf2txt.py -V -c euc-jp -o output.html samples/jo.pdf
    (extract a Japanese HTML file in vertical writing, CMap is required)

    $ pdf2txt.py -P mypassword -o output.txt secret.pdf
    (extract a text from an encrypted PDF file)

"""

import argparse
import sys

from pdfminer.pdfparser import PDFDocument, PDFParser
from pdfminer.pdfinterp import PDFResourceManager, PDFPageInterpreter, process_pdf
from pdfminer.pdfdevice import PDFDevice, TagExtractor
from pdfminer.converter import XMLConverter, HTMLConverter, TextConverter
from pdfminer.cmapdb import CMapDB
from pdfminer.layout import LAParams
from pdfminer.image import ImageWriter


def main():
    parser = argparse.ArgumentParser(description='Convert PDF into text.')
    parser.add_argument('file', nargs='*', type=argparse.FileType('rb'), default=sys.stdin, help='file(s) to convert')
    parser.add_argument('-d', metavar='debug', nargs='?', default=argparse.SUPPRESS, type=int, help='debug level')
    parser.add_argument('-C', '--nocache', dest='cache', action='store_false', help='prevent object caching (slower)')
    parser.add_argument('-p', metavar='page', nargs='+', default=[], type=int, help='page number(s) (space separated)')
    parser.add_argument('-m', metavar='maxpages', default=0, type=int, help='maximum number of pages to extract')
    parser.add_argument('-P', metavar='password', default='', help='pdf password')
    parser.add_argument('-o', metavar='outfile', type=argparse.FileType('w'), default=sys.stdout,
                        help='output file name (default: stdout)')
    parser.add_argument('-O', metavar='directory', type=ImageWriter, help='extract images and save to directory')
    parser.add_argument('-t', metavar='outtype', help='output type (text, html, xml, tag)')
    parser.add_argument('-c', metavar='codec', default='utf-8', help='output text encoding (default: %(default)s)')
    lagroup = parser.add_argument_group(title='layout analysis')
    lagroup.add_argument('-n', action='store_true', help='disable layout analysis')
    lagroup.add_argument('-A', action='store_true', help='force layout analysis on all text')
    lagroup.add_argument('-V', action='store_true', help='detect vertical text')
    lagroup.add_argument('-M', metavar='char_margin', type=float, help='custom character margin')
    lagroup.add_argument('-L', metavar='line_margin', type=float, help='custom line margin')
    lagroup.add_argument('-W', metavar='word_margin', type=float, help='custom word margin')
    lagroup.add_argument('-F', metavar='boxes_flow', type=float, help='custom boxes flow')
    lagroup.add_argument('-Y', metavar='layout_mode', default='normal', help='layout mode for HTML (normal, exact, loose)')
    lagroup.add_argument('-s', metavar='scale', default=1, type=float, help='output scaling for HTML')
    args = parser.parse_args()

    debug = int(args.d or 1) if 'd' in args else 0
    PDFDocument.debug = debug
    PDFParser.debug = debug
    CMapDB.debug = debug
    PDFResourceManager.debug = debug
    PDFPageInterpreter.debug = debug
    PDFDevice.debug = debug

    laparams = LAParams()
    if args.n:
        laparams = None
    else:
        laparams.all_texts = args.A
        laparams.detect_vertical = args.V
        if args.M:
            laparams.char_margin = args.M
        if args.L:
            laparams.line_margin = args.L
        if args.W:
            laparams.word_margin = args.W
        if args.F:
            laparams.boxes_flow = args.F

    rsrcmgr = PDFResourceManager(caching=args.cache)
    outtype = args.t
    if not outtype:
        if args.o:
            if args.o.name.endswith('.htm') or args.o.name.endswith('.html'):
                outtype = 'html'
            elif args.o.name.endswith('.xml'):
                outtype = 'xml'
            elif args.o.name.endswith('.tag'):
                outtype = 'tag'
    if outtype == 'xml':
        device = XMLConverter(rsrcmgr, args.o, codec=args.c, laparams=laparams, imagewriter=args.O)
    elif outtype == 'html':
        device = HTMLConverter(rsrcmgr, args.o, codec=args.c, scale=args.s, layoutmode=args.Y,
                               laparams=laparams, imagewriter=args.O)
    elif outtype == 'tag':
        device = TagExtractor(rsrcmgr, args.o, codec=args.c)
    else:
        device = TextConverter(rsrcmgr, args.o, codec=args.c, laparams=laparams, imagewriter=args.O)
    for fp in args.file:
        process_pdf(rsrcmgr, device, fp, [i-1 for i in args.p], maxpages=args.m, password=args.P,
                    caching=args.cache, check_extractable=True)
        fp.close()
    device.close()
    args.o.close()


if __name__ == '__main__':
    sys.exit(main())
