#!/usr/bin/env python2

try:
    import cprofile as profile
except ImportError:
    import profile
import pstats


def profile_function(module, func, args):
    """Profile a function"""
    module = __import__(module, fromlist=1)
    func = getattr(module, func)
    profile.runctx('func(%s)' % args, globals(), locals(), 'stats')
    p = pstats.Stats('stats')
    p.strip_dirs().sort_stats('cumulative').print_stats()


if __name__ == '__main__':
    path = '../samples/nonfree/i1040nr.pdf'
    outpath = '../samples/nonfree/i1040nrall.txt'
    profile_function('pdfminer.pdf2txt', 'main', "['%s', '-p', '1', '2', '3', '4', '-V', '-o', '%s']" % (path, outpath))
