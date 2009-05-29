# cmdline.py
#
# Copyright (c) 2008-2009 Trevor Caira
#
# Permission is hereby granted, free of charge, to any person obtaining
# a copy of this software and associated documentation files (the
# "Software"), to deal in the Software without restriction, including
# without limitation the rights to use, copy, modify, merge, publish,
# distribute, sublicense, and/or sell copies of the Software, and to
# permit persons to whom the Software is furnished to do so, subject to
# the following conditions:
#
# The above copyright notice and this permission notice shall be
# included in all copies or substantial portions of the Software.
#
# THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND,
# EXPRESS OR IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF
# MERCHANTABILITY, FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT.
# IN NO EVENT SHALL THE AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY
# CLAIM, DAMAGES OR OTHER LIABILITY, WHETHER IN AN ACTION OF CONTRACT,
# TORT OR OTHERWISE, ARISING FROM, OUT OF OR IN CONNECTION WITH THE
# SOFTWARE OR THE USE OR OTHER DEALINGS IN THE SOFTWARE.

import locale
from optparse import OptionParser
import os

from timebook import get_version
from timebook.db import Database
from timebook.commands import commands, run_command
from timebook.config import parse_config
from timebook.cmdutil import AmbiguousLookup, NoMatch

confdir = os.path.expanduser(os.path.join('~', '.config', 'timebook'))
DEFAULTS = {'config': os.path.join(confdir, 'timebook.ini'),
            'timebook': os.path.join(confdir, 'sheets.db'),
            'encoding': locale.getpreferredencoding()}

def make_parser():
    cmd_descs = ['%s - %s' % (k, commands[k].description) for k
                 in sorted(commands)]
    parser = OptionParser(usage='''usage: %%prog [OPTIONS] COMMAND \
[ARGS...]

where COMMAND is one of:
    %s''' % '\n    '.join(cmd_descs), version=get_version())
    parser.disable_interspersed_args()
    parser.add_option('-C', '--config', dest='config',
                      default=DEFAULTS['config'], help='Specify an \
alternate configuration file (default: "%s").' % DEFAULTS['config'])
    parser.add_option('-b', '--timebook', dest='timebook',
                      default=DEFAULTS['timebook'], help='Specify an \
alternate timebook file (default: "%s").' % DEFAULTS['timebook'])
    parser.add_option('-e', '--encoding', dest='encoding',
                      default=DEFAULTS['encoding'], help='Specify an \
alternate encoding to decode command line options and arguments (default: \
"%s")' % DEFAULTS['encoding'])
    return parser

def parse_options(parser):
    options, args = parser.parse_args()
    encoding = options.__dict__.pop('encoding')
    try:
        options.__dict__ = dict((k, v.decode(encoding)) for (k, v) in
                                options.__dict__.iteritems())
        args = [a.decode(encoding) for a in args]
    except LookupError:
        parser.error('unknown encoding %s' % encoding)

    if len(args) < 1:
        # default to ``t now``
        args = ['now'] + args
    return options, args


def run_from_cmdline():
    parser = make_parser()
    options, args = parse_options(parser)
    config = parse_config(options.config)
    db = Database(options.timebook, config)
    cmd, args = args[0], args[1:]
    try:
        run_command(db, cmd, args)
    except NoMatch, e:
        parser.error('%s' % e.args[0])
    except AmbiguousLookup, e:
        parser.error('%s\n    %s' % (e.args[0], ' '.join(e.args[1])))
