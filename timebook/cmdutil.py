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

import datetime
import time
import re

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

today_str = time.strftime("%Y-%m-%d", datetime.datetime.now().timetuple())
matches = [(re.compile(r'^\d+:\d+$'), today_str + " ", ":00"),
           (re.compile(r'^\d+:\d+:\d+$'), today_str + " ", ""),
           (re.compile(r'^\d+-\d+-\d+$'), "", " 00:00:00"),
           (re.compile(r'^\d+-\d+-\d+\s+\d+:\d+$'), "", ":00"),
           (re.compile(r'^\d+-\d+-\d+\s+\d+:\d+:\d+$'), "", ""),
          ]
fmt = "%Y-%m-%d %H:%M:%S"
def parse_date_time(dt_str):
    for (patt, prepend, postpend) in matches:
        if patt.match(dt_str):
            res = time.strptime(prepend + dt_str + postpend, fmt)
            return int(time.mktime(res))
    raise ValueError, "%s is not in a valid time format"%dt_str

def parse_date_time_or_now(dt_str):
    if dt_str:
        return parse_date_time(dt_str)
    else:
        return int(time.time())


def timedelta_hms_display(timedelta):
    hours = timedelta.days * 24 + timedelta.seconds / 3600
    minutes = timedelta.seconds / 60 % 60
    seconds = timedelta.seconds % 60
    return '%02d:%02d:%02d' % (hours, minutes, seconds)
