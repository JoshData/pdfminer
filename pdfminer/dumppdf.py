#!/usr/bin/env python2
"""
dumppdf.py - dump pdf contents in XML format.

This script dumps the internal contents of a PDF file in pseudo-XML format. This program is primarily for debugging
purposes, but it's also possible to extract some meaningful contents (such as images).

Examples

    $ dumppdf.py -a foo.pdf
    (dump all the headers and contents, except stream objects)

    $ dumppdf.py -T foo.pdf
    (dump the table of contents)

    $ dumppdf.py -c raw -i 6 foo.pdf > pic.jpg
    (extract a JPEG image)

"""

import argparse
import os
import sys
import re

from pdfminer.psparser import PSKeyword, PSLiteral
from pdfminer.pdfparser import PDFDocument, PDFParser, PDFNoOutlines
from pdfminer.pdftypes import PDFStream, PDFObjRef, resolve1, stream_value


ESC_PAT = re.compile(r'[\000-\037&<>()"\042\047\134\177-\377]')


def e(s):
    return ESC_PAT.sub(lambda m: '&#%d;' % ord(m.group(0)), s)


def dumpxml(out, obj, codec=None):
    if obj is None:
        out.write('<null />')
        return
    
    if isinstance(obj, dict):
        out.write('<dict size="%d">\n' % len(obj))
        for (k, v) in obj.iteritems():
            out.write('<key>%s</key>\n' % k)
            out.write('<value>')
            dumpxml(out, v)
            out.write('</value>\n')
        out.write('</dict>')
        return

    if isinstance(obj, list):
        out.write('<list size="%d">\n' % len(obj))
        for v in obj:
            dumpxml(out, v)
            out.write('\n')
        out.write('</list>')
        return

    if isinstance(obj, str):
        out.write('<string size="%d">%s</string>' % (len(obj), e(obj)))
        return

    if isinstance(obj, PDFStream):
        if codec == 'raw':
            out.write(obj.get_rawdata())
        elif codec == 'binary':
            out.write(obj.get_data())
        else:
            out.write('<stream>\n<props>\n')
            dumpxml(out, obj.attrs)
            out.write('\n</props>\n')
            if codec == 'text':
                data = obj.get_data()
                out.write('<data size="%d">%s</data>\n' % (len(data), e(data)))
            out.write('</stream>')
        return

    if isinstance(obj, PDFObjRef):
        out.write('<ref id="%d" />' % obj.objid)
        return

    if isinstance(obj, PSKeyword):
        out.write('<keyword>%s</keyword>' % obj.name)
        return

    if isinstance(obj, PSLiteral):
        out.write('<literal>%s</literal>' % obj.name)
        return

    if isinstance(obj, int) or isinstance(obj, float):
        out.write('<number>%s</number>' % obj)
        return

    raise TypeError(obj)


def dumptrailers(out, doc):
    for xref in doc.xrefs:
        out.write('<trailer>\n')
        dumpxml(out, xref.trailer)
        out.write('\n</trailer>\n\n')
    return


def dumpallobjs(out, doc, codec=None):
    out.write('<pdf>')
    for xref in doc.xrefs:
        for objid in xref.get_objids():
            try:
                obj = doc.getobj(objid)
                if obj is None:
                    continue
                out.write('<object id="%d">\n' % objid)
                dumpxml(out, obj, codec=codec)
                out.write('\n</object>\n\n')
            except:
                raise
    dumptrailers(out, doc)
    out.write('</pdf>')
    return


def dumpoutline(outfp, fp, objids, pagenos, password='', dumpall=False, codec=None):
    doc = PDFDocument()
    parser = PDFParser(fp)
    parser.set_document(doc)
    doc.set_parser(parser)
    doc.initialize(password)
    pages = dict( (page.pageid, pageno) for (pageno,page) in enumerate(doc.get_pages()) )
    def resolve_dest(dest):
        if isinstance(dest, str):
            dest = resolve1(doc.get_dest(dest))
        elif isinstance(dest, PSLiteral):
            dest = resolve1(doc.get_dest(dest.name))
        if isinstance(dest, dict):
            dest = dest['D']
        return dest
    try:
        outlines = doc.get_outlines()
        outfp.write('<outlines>\n')
        for (level, title, dest, a, se) in outlines:
            pageno = None
            if dest:
                dest = resolve_dest(dest)
                pageno = pages[dest[0].objid]
            elif a:
                action = a.resolve()
                if isinstance(action, dict):
                    subtype = action.get('S')
                    if subtype and repr(subtype) == '/GoTo' and action.get('D'):
                        dest = resolve_dest(action['D'])
                        pageno = pages[dest[0].objid]
            s = e(title).encode('utf-8', 'xmlcharrefreplace')
            outfp.write('<outline level="%r" title="%s">\n' % (level, s))
            if dest is not None:
                outfp.write('<dest>')
                dumpxml(outfp, dest)
                outfp.write('</dest>\n')
            if pageno is not None:
                outfp.write('<pageno>%r</pageno>\n' % pageno)
            outfp.write('</outline>\n')
        outfp.write('</outlines>\n')
    except PDFNoOutlines:
        pass
    parser.close()
    fp.close()
    return


def extractembedded(outfp, fp, objids, pagenos, password='', dumpall=False, codec=None):
    doc = PDFDocument()
    parser = PDFParser(fp)
    parser.set_document(doc)
    doc.set_parser(parser)
    doc.initialize(password)

    cwd = os.path.normpath(os.getcwd()) + '/'
    for xref in doc.xrefs:
        for objid in xref.get_objids():
            obj = doc.getobj(objid)
            if isinstance(obj, dict):
                objtype = obj.get('Type', '')
                if isinstance(objtype, PSLiteral) and objtype.name == 'Filespec':
                    filename = obj['UF'] or obj['F']
                    fileref = obj['EF']['F']
                    fileobj = doc.getobj(fileref.objid)
                    if not isinstance(fileobj, PDFStream):
                        raise Exception("unable to process PDF: reference for %s is not a PDFStream" % filename)
                    if not isinstance(fileobj['Type'], PSLiteral) or not fileobj['Type'].name == 'EmbeddedFile':
                        raise Exception("unable to process PDF: reference for %s is not an EmbeddedFile" % filename)

                    print "extracting", filename
                    absfilename = os.path.normpath(os.path.abspath(filename))
                    if not absfilename.startswith(cwd):
                        raise Exception("filename %s is trying to escape to parent directories." % filename)

                    dirname = os.path.dirname(absfilename)
                    if not os.path.isdir(dirname):
                        os.makedirs(dirname)

                    # don't overwrite anything
                    fd = os.open(absfilename, os.O_WRONLY | os.O_CREAT | os.O_EXCL)
                    f = os.fdopen(fd, 'wb')
                    f.write(fileobj.get_data())
                    f.close()


def dumppdf(outfp, fp, objids, pagenos, password='',
            dumpall=False, codec=None):
    doc = PDFDocument()
    parser = PDFParser(fp)
    parser.set_document(doc)
    doc.set_parser(parser)
    doc.initialize(password)
    if objids:
        for objid in objids:
            obj = doc.getobj(objid)
            dumpxml(outfp, obj, codec=codec)
    if pagenos:
        for (pageno,page) in enumerate(doc.get_pages()):
            if pageno in pagenos:
                if codec:
                    for obj in page.contents:
                        obj = stream_value(obj)
                        dumpxml(outfp, obj, codec=codec)
                else:
                    dumpxml(outfp, page.attrs)
    if dumpall:
        dumpallobjs(outfp, doc, codec=codec)
    if (not objids) and (not pagenos) and (not dumpall):
        dumptrailers(outfp, doc)
    fp.close()
    if codec not in ('raw', 'binary'):
        outfp.write('\n')
    return


def main():
    parser = argparse.ArgumentParser(description='Dump pdf contents in XML format.')
    parser.add_argument('file', nargs='*', type=argparse.FileType('rb'), default=sys.stdin, help='file(s) to dump')
    parser.add_argument('-d', metavar='debug', nargs='?', default=argparse.SUPPRESS, type=int, help='debug level')
    group = parser.add_mutually_exclusive_group()
    group.add_argument('-a', '--dumpall', action='store_true', help='dump all objects, not just trailer')
    group.add_argument('-T', '--dumpoutline', action='store_true', help='dump table of contents')
    group.add_argument('-E', metavar='directory', help='extract embedded files and save to directory')
    parser.add_argument('-c', metavar='codec', help='output format of stream contents (raw, binary, text)')
    parser.add_argument('-P', metavar='password', default='', help='pdf password')
    parser.add_argument('-p', metavar='page', nargs='+', default=[], type=int, help='page number(s) (space separated)')
    parser.add_argument('-i', metavar='objid', nargs='+', default=[],  type=int, help='object id(s) (space separated)')
    parser.add_argument('-o', metavar='outfile', type=argparse.FileType('wb'), default=sys.stdout,
                        help='output file name (default: stdout)')
    args = parser.parse_args()
    debug = int(args.d or 1) if 'd' in args else 0
    PDFDocument.debug = debug
    PDFParser.debug = debug
    proc = dumppdf
    if args.dumpoutline:
        proc = dumpoutline
    elif args.E:
        proc = extractembedded
        os.chdir(args.E)
    for fp in args.file:
        proc(args.o, fp, args.i, [i-1 for i in args.p], args.P, args.dumpall, args.c)
        pass


if __name__ == '__main__':
    sys.exit(main())
