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

from optparse import OptionParser
import os

from timebook.db import Database
from timebook.commands import commands, run_command
from timebook.config import parse_config
from timebook.cmdutil import AmbiguousLookup, NoMatch

confdir = os.path.expanduser(os.path.join('~', '.config', 'timebook'))
DEFAULTS = {'config': os.path.join(confdir, 'timebook.ini'),
            'timebook': os.path.join(confdir, 'sheets.db')}

def parse_options():
    cmd_descs = ['%s - %s' % (k, commands[k].description) for k
                 in sorted(commands)]
    parser = OptionParser(usage='''usage: %%prog [OPTIONS] COMMAND \
[ARGS...]

where COMMAND is one of:
    %s''' % '\n    '.join(cmd_descs))
    parser.disable_interspersed_args()
    parser.add_option('-C', '--config', dest='config',
                      default=DEFAULTS['config'], help='Specify an \
alternate configuration file (default: %r).' % DEFAULTS['config'])
    parser.add_option('-b', '--timebook', dest='timebook',
                      default=DEFAULTS['timebook'], help='Specify an \
alternate timebook file (default: %r).' % DEFAULTS['timebook'])
    options, args = parser.parse_args()
    if len(args) < 1:
        parser.error('no command specified')
    return options, args

def run_from_cmdline():
    options, args = parse_options()
    config = parse_config(options.config)
    db = Database(options.timebook, config)
    cmd, args = args[0], args[1:]
    try:
        run_command(db, cmd, args)
    except NoMatch, e:
        raise SystemExit, 'error: %s' % e.args[0]
    except AmbiguousLookup, e:
        raise SystemExit, 'error: %s\n    %s' % (e.args[0],
                                                 ' '.join(e.args[1]))
