#!/usr/bin/env python2

import logging
import re

try:
    from io import StringIO
except ImportError:
    from io import StringIO
from .cmapdb import CMapDB, CMap
from .psparser import PSTypeError, PSEOF
from .psparser import PSKeyword, literal_name, keyword_name
from .psparser import PSStackParser
from .psparser import LIT, KWD, handle_error
from .pdftypes import PDFException, PDFStream, PDFObjRef
from .pdftypes import resolve1
from .pdftypes import list_value, dict_value, stream_value
from .pdffont import PDFFontError
from .pdffont import PDFType1Font, PDFTrueTypeFont, PDFType3Font
from .pdffont import PDFCIDFont
from .pdfparser import PDFDocument, PDFParser
from .pdfcolor import PDFColorSpace
from .pdfcolor import PREDEFINED_COLORSPACE
from .utils import choplist
from .utils import mult_matrix, MATRIX_IDENTITY


log = logging.getLogger('pdfminer.pdfinterp')


class PDFResourceError(PDFException):
    pass


class PDFInterpreterError(PDFException):
    pass


LITERAL_PDF = LIT('PDF')
LITERAL_TEXT = LIT('Text')
LITERAL_FONT = LIT('Font')
LITERAL_FORM = LIT('Form')
LITERAL_IMAGE = LIT('Image')


class PDFTextState(object):

    def __init__(self):
        self.font = None
        self.fontsize = 0
        self.charspace = 0
        self.wordspace = 0
        self.scaling = 100
        self.leading = 0
        self.render = 0
        self.rise = 0
        self.reset()
        # self.matrix is set
        # self.linematrix is set

    def __repr__(self):
        return ('<PDFTextState: font=%r, fontsize=%r, charspace=%r, wordspace=%r, '
                ' scaling=%r, leading=%r, render=%r, rise=%r, '
                ' matrix=%r, linematrix=%r>' %
                (self.font, self.fontsize, self.charspace, self.wordspace, self.scaling, self.leading, self.render,
                 self.rise, self.matrix, self.linematrix))

    def copy(self):
        obj = PDFTextState()
        obj.font = self.font
        obj.fontsize = self.fontsize
        obj.charspace = self.charspace
        obj.wordspace = self.wordspace
        obj.scaling = self.scaling
        obj.leading = self.leading
        obj.render = self.render
        obj.rise = self.rise
        obj.matrix = self.matrix
        obj.linematrix = self.linematrix
        return obj

    def reset(self):
        self.matrix = MATRIX_IDENTITY
        self.linematrix = (0, 0)


class PDFGraphicState(object):

    def __init__(self):
        self.linewidth = 0
        self.linecap = None
        self.linejoin = None
        self.miterlimit = None
        self.dash = None
        self.intent = None
        self.flatness = None

    def copy(self):
        obj = PDFGraphicState()
        obj.linewidth = self.linewidth
        obj.linecap = self.linecap
        obj.linejoin = self.linejoin
        obj.miterlimit = self.miterlimit
        obj.dash = self.dash
        obj.intent = self.intent
        obj.flatness = self.flatness
        return obj

    def __repr__(self):
        return ('<PDFGraphicState: linewidth=%r, linecap=%r, linejoin=%r, '
                ' miterlimit=%r, dash=%r, intent=%r, flatness=%r>' %
                (self.linewidth, self.linecap, self.linejoin, self.miterlimit, self.dash, self.intent, self.flatness))


class PDFResourceManager(object):
    """Repository of shared resources.
    
    ResourceManager facilitates reuse of shared resources
    such as fonts and images so that large objects are not
    allocated multiple times.
    """

    def __init__(self, caching=True):
        self.caching = caching
        self._cached_fonts = {}

    def get_procset(self, procs):
        for proc in procs:
            if proc is LITERAL_PDF:
                pass
            elif proc is LITERAL_TEXT:
                pass
            else:
                #raise PDFResourceError('ProcSet %r is not supported.' % proc)
                pass

    def get_cmap(self, cmapname, strict=False):
        try:
            return CMapDB.get_cmap(cmapname)
        except CMapDB.CMapNotFound:
            if strict:
                raise
            return CMap()

    def get_font(self, objid, spec):
        if objid and objid in self._cached_fonts:
            font = self._cached_fonts[objid]
        else:
            log.info('get_font: create: objid=%r, spec=%r', objid, spec)
            if spec['Type'] is not LITERAL_FONT:
                handle_error(PDFFontError, 'Type is not /Font')
            # Create a Font object.
            if 'Subtype' in spec:
                subtype = literal_name(spec['Subtype'])
            else:
                handle_error(PDFFontError, 'Font Subtype is not specified.')
                subtype = 'Type1'
            if subtype in ('Type1', 'MMType1'):
                # Type1 Font
                font = PDFType1Font(self, spec)
            elif subtype == 'TrueType':
                # TrueType Font
                font = PDFTrueTypeFont(self, spec)
            elif subtype == 'Type3':
                # Type3 Font
                font = PDFType3Font(self, spec)
            elif subtype in ('CIDFontType0', 'CIDFontType2'):
                # CID Font
                font = PDFCIDFont(self, spec)
            elif subtype == 'Type0':
                # Type0 Font
                dfonts = list_value(spec['DescendantFonts'])
                assert dfonts
                subspec = dict_value(dfonts[0]).copy()
                for k in ('Encoding', 'ToUnicode'):
                    if k in spec:
                        subspec[k] = resolve1(spec[k])
                font = self.get_font(None, subspec)
            else:
                handle_error(PDFFontError, 'Invalid Font spec: %r' % spec)
                font = PDFType1Font(self, spec) # this is so wrong!
            if objid and self.caching:
                self._cached_fonts[objid] = font
        return font


class PDFContentParser(PSStackParser):

    def __init__(self, streams):
        self.streams = streams
        self.istream = 0
        PSStackParser.__init__(self, None)

    def fillfp(self):
        if not self.fp:
            if self.istream < len(self.streams):
                strm = stream_value(self.streams[self.istream])
                self.istream += 1
            else:
                raise PSEOF('Unexpected EOF, file truncated?')
            self.fp = StringIO(strm.get_data())

    def seek(self, pos):
        self.fillfp()
        PSStackParser.seek(self, pos)

    def fillbuf(self):
        if self.charpos < len(self.buf):
            return
        while 1:
            self.fillfp()
            self.bufpos = self.fp.tell()
            self.buf = self.fp.read(self.BUFSIZ)
            if self.buf:
                break
            self.fp = None
        self.charpos = 0

    def get_inline_data(self, pos, target='EI'):
        self.seek(pos)
        i = 0
        data = ''
        while i <= len(target):
            self.fillbuf()
            if i:
                c = self.buf[self.charpos]
                data += c
                self.charpos += 1
                if len(target) <= i and c.isspace():
                    i += 1
                elif i < len(target) and c == target[i]:
                    i += 1
                else:
                    i = 0
            else:
                try:
                    j = self.buf.index(target[0], self.charpos)
                    #print 'found', (0, self.buf[j:j+10])
                    data += self.buf[self.charpos:j + 1]
                    self.charpos = j + 1
                    i = 1
                except ValueError:
                    data += self.buf[self.charpos:]
                    self.charpos = len(self.buf)
        data = data[:-(len(target) + 1)] # strip the last part
        data = re.sub(r'(\x0d\x0a|[\x0d\x0a])$', '', data)
        return pos, data

    def flush(self):
        self.add_results(*self.popall())

    KEYWORD_BI = KWD('BI')
    KEYWORD_ID = KWD('ID')
    KEYWORD_EI = KWD('EI')

    def do_keyword(self, pos, token):
        if token is self.KEYWORD_BI:
            # inline image within a content stream
            self.start_type(pos, 'inline')
        elif token is self.KEYWORD_ID:
            try:
                (_, objs) = self.end_type('inline')
                if len(objs) % 2 != 0:
                    raise PSTypeError('Invalid dictionary construct: %r' % objs)
                d = dict((literal_name(k), v) for (k, v) in choplist(2, objs))
                (pos, data) = self.get_inline_data(pos + len('ID '))
                obj = PDFStream(d, data)
                self.push((pos, obj))
                self.push((pos, self.KEYWORD_EI))
            except PSTypeError as e:
                handle_error(type(e), str(e))
        else:
            self.push((pos, token))


class PDFPageInterpreter(object):

    def __init__(self, rsrcmgr, device):
        self.rsrcmgr = rsrcmgr
        self.device = device

    def dup(self):
        return PDFPageInterpreter(self.rsrcmgr, self.device)

    def init_resources(self, resources):
        """Prepare the fonts and XObjects listed in the Resource attribute."""
        self.resources = resources
        self.fontmap = {}
        self.xobjmap = {}
        self.csmap = PREDEFINED_COLORSPACE.copy()
        if not resources:
            return

        def get_colorspace(spec):
            if isinstance(spec, list):
                name = literal_name(spec[0])
            else:
                name = literal_name(spec)
            if name == 'ICCBased' and isinstance(spec, list) and 2 <= len(spec):
                return PDFColorSpace(name, stream_value(spec[1])['N'])
            elif name == 'DeviceN' and isinstance(spec, list) and 2 <= len(spec):
                return PDFColorSpace(name, len(list_value(spec[1])))
            else:
                return PREDEFINED_COLORSPACE.get(name)
        for (k, v) in dict_value(resources).items():
            log.debug('Resource: %r: %r', k, v)
            if k == 'Font':
                for (fontid, spec) in dict_value(v).items():
                    objid = None
                    if isinstance(spec, PDFObjRef):
                        objid = spec.objid
                    spec = dict_value(spec)
                    self.fontmap[fontid] = self.rsrcmgr.get_font(objid, spec)
            elif k == 'ColorSpace':
                for (csid, spec) in dict_value(v).items():
                    self.csmap[csid] = get_colorspace(resolve1(spec))
            elif k == 'ProcSet':
                self.rsrcmgr.get_procset(list_value(v))
            elif k == 'XObject':
                for (xobjid, xobjstrm) in dict_value(v).items():
                    self.xobjmap[xobjid] = xobjstrm

    def init_state(self, ctm):
        """Initialize the text and graphic states for rendering a page."""
        # gstack: stack for graphical states.
        self.gstack = []
        self.ctm = ctm
        self.device.set_ctm(self.ctm)
        self.textstate = PDFTextState()
        self.graphicstate = PDFGraphicState()
        self.curpath = []
        # argstack: stack for command arguments.
        self.argstack = []
        # set some global states.
        self.scs = self.ncs = None
        if self.csmap:
            self.scs = self.ncs = list(self.csmap.values())[0]

    def push(self, obj):
        self.argstack.append(obj)

    def pop(self, n):
        if n == 0:
            return []
        x = self.argstack[-n:]
        self.argstack = self.argstack[:-n]
        return x

    def get_current_state(self):
        return self.ctm, self.textstate.copy(), self.graphicstate.copy()

    def set_current_state(self, state):
        (self.ctm, self.textstate, self.graphicstate) = state
        self.device.set_ctm(self.ctm)

    def do_q(self):
        """gsave"""
        self.gstack.append(self.get_current_state())

    def do_Q(self):
        """grestore"""
        if self.gstack:
            self.set_current_state(self.gstack.pop())

    def do_cm(self, a1, b1, c1, d1, e1, f1):
        """concat-matrix"""
        self.ctm = mult_matrix((a1,b1,c1,d1,e1,f1), self.ctm)
        self.device.set_ctm(self.ctm)

    def do_w(self, linewidth):
        """setlinewidth"""
        self.graphicstate.linewidth = linewidth

    def do_J(self, linecap):
        """setlinecap"""
        self.graphicstate.linecap = linecap

    def do_j(self, linejoin):
        """setlinejoin"""
        self.graphicstate.linejoin = linejoin

    def do_M(self, miterlimit):
        """setmiterlimit"""
        self.graphicstate.miterlimit = miterlimit

    def do_d(self, dash, phase):
        """setdash"""
        self.graphicstate.dash = (dash, phase)

    def do_ri(self, intent):
        """setintent"""
        self.graphicstate.intent = intent

    def do_i(self, flatness):
        """setflatness"""
        self.graphicstate.flatness = flatness

    def do_gs(self, name):
        """load-gstate"""
        #XXX
        return

    def do_m(self, x, y):
        """moveto"""
        self.curpath.append(('m', x, y))

    def do_l(self, x, y):
        """lineto"""
        self.curpath.append(('l', x, y))

    def do_c(self, x1, y1, x2, y2, x3, y3):
        """curveto"""
        self.curpath.append(('c', x1, y1, x2, y2, x3, y3))

    def do_v(self, x2, y2, x3, y3):
        """urveto"""
        self.curpath.append(('v', x2, y2, x3, y3))

    def do_y(self, x1, y1, x3, y3):
        """rveto"""
        self.curpath.append(('y', x1, y1, x3, y3))

    def do_h(self):
        """closepath"""
        self.curpath.append(('h',))

    def do_re(self, x, y, w, h):
        """rectangle"""
        self.curpath.append(('m', x, y))
        self.curpath.append(('l', x + w, y))
        self.curpath.append(('l', x + w, y + h))
        self.curpath.append(('l', x, y + h))
        self.curpath.append(('h',))

    def do_S(self):
        """stroke"""
        self.device.paint_path(self.graphicstate, True, False, False, self.curpath)
        self.curpath = []

    def do_s(self):
        """close-and-stroke"""
        self.do_h()
        self.do_S()

    def do_f(self):
        """fill"""
        self.device.paint_path(self.graphicstate, False, True, False, self.curpath)
        self.curpath = []

    # fill (obsolete)
    do_F = do_f

    def do_f_a(self):
        """fill-even-odd"""
        self.device.paint_path(self.graphicstate, False, True, True, self.curpath)
        self.curpath = []

    def do_B(self):
        """fill-and-stroke"""
        self.device.paint_path(self.graphicstate, True, True, False, self.curpath)
        self.curpath = []

    def do_B_a(self):
        """fill-and-stroke-even-odd"""
        self.device.paint_path(self.graphicstate, True, True, True, self.curpath)
        self.curpath = []

    def do_b(self):
        """close-fill-and-stroke"""
        self.do_h()
        self.do_B()

    def do_b_a(self):
        """close-fill-and-stroke-even-odd"""
        self.do_h()
        self.do_B_a()

    def do_n(self):
        """close-only"""
        self.curpath = []

    def do_W(self):
        """clip"""
        return

    def do_W_a(self):
        """clip-even-odd"""
        return

    def do_CS(self, name):
        """setcolorspace-stroking"""
        self.scs = self.csmap[literal_name(name)]

    def do_cs(self, name):
        """setcolorspace-non-strokine"""
        self.ncs = self.csmap[literal_name(name)]

    def do_G(self, gray):
        """setgray-stroking"""
        #self.do_CS(LITERAL_DEVICE_GRAY)
        return

    def do_g(self, gray):
        """setgray-non-stroking"""
        #self.do_cs(LITERAL_DEVICE_GRAY)
        return

    def do_RG(self, r, g, b):
        """setrgb-stroking"""
        #self.do_CS(LITERAL_DEVICE_RGB)
        return

    def do_rg(self, r, g, b):
        """setrgb-non-stroking"""
        #self.do_cs(LITERAL_DEVICE_RGB)
        return

    def do_K(self, c, m, y, k):
        """setcmyk-stroking"""
        #self.do_CS(LITERAL_DEVICE_CMYK)
        return

    def do_k(self, c, m, y, k):
        """setcmyk-non-stroking"""
        #self.do_cs(LITERAL_DEVICE_CMYK)
        return

    def do_SCN(self):
        """setcolor"""
        if self.scs:
            n = self.scs.ncomponents
        else:
            handle_error(PDFInterpreterError, 'No colorspace specified!')
            n = 1
        self.pop(n)

    def do_scn(self):
        if self.ncs:
            n = self.ncs.ncomponents
        else:
            handle_error(PDFInterpreterError, 'No colorspace specified!')
            n = 1
        self.pop(n)

    def do_SC(self):
        self.do_SCN()

    def do_sc(self):
        self.do_scn()

    def do_sh(self, name):
        """sharing-name"""
        return

    def do_BT(self):
        """begin-text"""
        self.textstate.reset()

    def do_ET(self):
        """end-text"""
        return

    def do_BX(self):
        """begin-compat"""
        return

    def do_EX(self):
        """end-compat"""
        return

    def do_MP(self, tag):
        """marked content operators"""
        self.device.do_tag(tag)

    def do_DP(self, tag, props):
        self.device.do_tag(tag, props)

    def do_BMC(self, tag):
        self.device.begin_tag(tag)

    def do_BDC(self, tag, props):
        self.device.begin_tag(tag, props)

    def do_EMC(self):
        self.device.end_tag()

    def do_Tc(self, space):
        """setcharspace"""
        self.textstate.charspace = space

    def do_Tw(self, space):
        """setwordspace"""
        self.textstate.wordspace = space

    def do_Tz(self, scale):
        """textscale"""
        self.textstate.scaling = scale

    def do_TL(self, leading):
        """setleading"""
        self.textstate.leading = -leading

    def do_Tf(self, fontid, fontsize):
        """selectfont"""
        try:
            self.textstate.font = self.fontmap[literal_name(fontid)]
        except KeyError:
            handle_error(PDFInterpreterError, 'Undefined Font id: %r' % fontid)
            self.textstate.font = PDFType1Font(self.rsrcmgr, {'BaseFont': 'Times-Roman'})
        self.textstate.fontsize = fontsize

    def do_Tr(self, render):
        """setrendering"""
        self.textstate.render = render

    def do_Ts(self, rise):
        """settextrise"""
        self.textstate.rise = rise

    def do_Td(self, tx, ty):
        """text-move"""
        (a, b, c, d, e, f) = self.textstate.matrix
        self.textstate.matrix = (a, b, c, d, tx * a + ty * c + e, tx * b + ty * d + f)
        self.textstate.linematrix = (0, 0)
        #print >>sys.stderr, 'Td(%r,%r): %r' % (tx,ty,self.textstate)

    def do_TD(self, tx, ty):
        """text-move"""
        (a, b, c, d, e, f) = self.textstate.matrix
        self.textstate.matrix = (a, b, c, d, tx * a + ty * c + e, tx * b + ty * d + f)
        self.textstate.leading = ty
        self.textstate.linematrix = (0, 0)
        #print >>sys.stderr, 'TD(%r,%r): %r' % (tx,ty,self.textstate)

    def do_Tm(self, a, b, c, d, e, f):
        """textmatrix"""
        self.textstate.matrix = (a, b, c, d, e, f)
        self.textstate.linematrix = (0, 0)

    def do_T_a(self):
        """nextline"""
        (a, b, c, d, e, f) = self.textstate.matrix
        self.textstate.matrix = (a, b, c, d, self.textstate.leading * c + e, self.textstate.leading * d + f)
        self.textstate.linematrix = (0, 0)

    def do_TJ(self, seq):
        """show-pos"""
        #print >>sys.stderr, 'TJ(%r): %r' % (seq,self.textstate)
        if self.textstate.font is None:
            handle_error(PDFInterpreterError, 'No font specified!')
            return
        self.device.render_string(self.textstate, seq)

    def do_Tj(self, s):
        """show"""
        self.do_TJ([s])

    def do__q(self, s):
        """quote"""
        self.do_T_a()
        self.do_TJ([s])

    def do__w(self, aw, ac, s):
        """doublequote"""
        self.do_Tw(aw)
        self.do_Tc(ac)
        self.do_TJ([s])

    def do_BI(self):
        """inline image"""
        # never called
        return

    def do_ID(self):  # never called
        return

    def do_EI(self, obj):
        try:
            if 'W' in obj and 'H' in obj:
                iobjid = str(id(obj))
                self.device.begin_figure(iobjid, (0, 0, 1, 1), MATRIX_IDENTITY)
                self.device.render_image(iobjid, obj)
                self.device.end_figure(iobjid)
        except TypeError:
            # Sometimes, 'obj' is a PSLiteral. I'm not sure why, but I'm guessing it's because it's malformed or
            # something. We can just ignore the thing.
            logging.warning('Malformed inline image')

    def do_Do(self, xobjid):
        """Invoke an XObject."""
        xobjid = literal_name(xobjid)
        try:
            xobj = stream_value(self.xobjmap[xobjid])
        except KeyError:
            handle_error(PDFInterpreterError, 'Undefined xobject id: %r' % xobjid)
            return
        log.info('Processing xobj: %r', xobj)
        subtype = xobj.get('Subtype')
        if subtype is LITERAL_FORM and 'BBox' in xobj:
            interpreter = self.dup()
            bbox = list_value(xobj['BBox'])
            matrix = list_value(xobj.get('Matrix', MATRIX_IDENTITY))
            # According to PDF reference 1.7 section 4.9.1, XObjects in 
            # earlier PDFs (prior to v1.2) use the page's Resources entry
            # instead of having their own Resources entry.
            resources = dict_value(xobj.get('Resources')) or self.resources.copy()
            self.device.begin_figure(xobjid, bbox, matrix)
            interpreter.render_contents(resources, [xobj], ctm=mult_matrix(matrix, self.ctm))
            self.device.end_figure(xobjid)
        elif subtype is LITERAL_IMAGE and 'Width' in xobj and 'Height' in xobj:
            self.device.begin_figure(xobjid, (0, 0, 1, 1), MATRIX_IDENTITY)
            self.device.render_image(xobjid, xobj)
            self.device.end_figure(xobjid)
        else:
            # unsupported xobject type.
            pass

    def process_page(self, page):
        log.info('Processing page: %r', page)
        (x0, y0, x1, y1) = page.mediabox
        if page.rotate == 90:
            ctm = (0, -1, 1, 0, -y0, x1)
        elif page.rotate == 180:
            ctm = (-1, 0, 0, -1, x1, y1)
        elif page.rotate == 270:
            ctm = (0, 1, -1, 0, y1, -x0)
        else:
            ctm = (1, 0, 0, 1, -x0, -y0)
        self.device.begin_page(page, ctm)
        self.render_contents(page.resources, page.contents, ctm=ctm)
        self.device.end_page(page)

    def render_contents(self, resources, streams, ctm=MATRIX_IDENTITY):
        """Render the content streams. This method may be called recursively. """
        log.info('render_contents: resources=%r, streams=%r, ctm=%r', resources, streams, ctm)
        self.init_resources(resources)
        self.init_state(ctm)
        self.execute(list_value(streams))

    def execute(self, streams):
        try:
            parser = PDFContentParser(streams)
        except PSEOF:
            # empty page
            return
        while 1:
            try:
                (_, obj) = parser.nextobject()
            except PSEOF:
                break
            if isinstance(obj, PSKeyword):
                name = keyword_name(obj)
                method = 'do_%s' % name.replace('*', '_a').replace('"', '_w').replace("'", '_q')
                if hasattr(self, method):
                    func = getattr(self, method)
                    nargs = func.__code__.co_argcount - 1
                    if nargs:
                        args = self.pop(nargs)
                        log.debug('exec: %s %r', name, args)
                        if len(args) == nargs:
                            func(*args)
                    else:
                        log.debug('exec: %s', name)
                        func()
                else:
                    handle_error(PDFInterpreterError, 'Unknown operator: %r' % name)
            else:
                self.push(obj)


class PDFTextExtractionNotAllowed(PDFInterpreterError):
    pass


def process_pdf(rsrcmgr, device, fp, pagenos=None, maxpages=0, password='', caching=True, check_extractable=True):
    # Create a PDF parser object associated with the file object.
    parser = PDFParser(fp)
    # Create a PDF document object that stores the document structure.
    doc = PDFDocument(caching=caching)
    # Connect the parser and document objects.
    parser.set_document(doc)
    doc.set_parser(parser)
    # Supply the document password for initialization.
    # (If no password is set, give an empty string.)
    doc.initialize(password)
    # Check if the document allows text extraction. If not, abort.
    if check_extractable and not doc.is_extractable:
        raise PDFTextExtractionNotAllowed('Text extraction is not allowed: %r' % fp)
    # Create a PDF interpreter object.
    interpreter = PDFPageInterpreter(rsrcmgr, device)
    # Process each page contained in the document.
    for (pageno, page) in enumerate(doc.get_pages()):
        if pagenos and (pageno not in pagenos):
            continue
        interpreter.process_page(page)
        if maxpages and maxpages <= pageno + 1:
            break
