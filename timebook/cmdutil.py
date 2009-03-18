# cmdutil.py
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

import time

class AmbiguousLookup(ValueError):
    pass

class NoMatch(ValueError):
    pass

def complete(it, lookup, key_desc):
    partial_match = None
    for i in it:
        if i == lookup:
            return i
        if i.startswith(lookup):
            if partial_match is not None:
                matches = sorted(i for i in it if i.startswith(lookup))
                raise AmbiguousLookup('ambiguous %s "%s":' %
                                      (key_desc, lookup), matches)
            partial_match = i
    if partial_match is None:
        raise NoMatch('no such %s "%s".' % (key_desc, lookup))
    else:
        return partial_match

def pprint_table(table, footer_row=False):
    if footer_row:
        check = table[:-1]
    else:
        check = table
    widths = [3 + max(len(row[col]) for row in check) for col
              in xrange(len(table[0]))]
    for row in table:
        # Don't pad the final column
        first_cols = [cell + ' ' * (spacing - len(cell))
                      for (cell, spacing) in zip(row[:-1], widths[:-1])]
        print ''.join(first_cols + [row[-1]])

def datetime_to_int(dt):
    return int(time.mktime(dt.timetuple()))
