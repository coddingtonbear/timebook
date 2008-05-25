#!/usr/bin/python
#
# Copyright (c) 2008 Trevor Caira
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

import cPickle as pickle
from datetime import datetime, timedelta
from optparse import OptionParser
import os
import time

DEFAULTS = {'timesheets':
    os.path.expanduser(os.path.join('~', '.config', 'timesheet',
                                    'timesheets.dat'))}

commands = {}
def command(desc):
    def decorator(func):
        globals()['commands'][func.func_code.co_name] = (func, desc)
        return func
    return decorator

def complete(dct, lookup, key_desc):
    partial_match = None
    for k, v in dct.iteritems():
        if k == lookup:
            return k, v
        if k.startswith(lookup):
            if partial_match is not None:
                raise ValueError('ambiguous %s %r' % (key_desc, lookup))
            partial_match = k, v
    if partial_match is None:
        raise ValueError('no such %s %r.' % (key_desc, lookup))
    else:
        return partial_match

def subdirs(path):
    path = os.path.abspath(path)
    last = path.find(os.path.sep)
    while True:
        if last == -1:
            break
        yield path[:last + 1]
        last = path.find(os.path.sep, last + 1)

def pprint_table(table):
    widths = [3 + max([len(row[col]) for row in table])
              for col in xrange(len(table[0]))]
    for row in table:
        print ''.join([cell + ' ' * (spacing - len(cell))
                       for (cell, spacing) in zip(row, widths)])

def pformat_timesheet(filename):
    f = file(filename)
    try:
        from pprint import PrettyPrinter
        return PrettyPrinter().pformat(pickle.loads(f.read()))
    finally:
        f.close()

def load(filename):
    # Timesheet format: list of 3-element lists:
    #   1. Time start was called
    #   2. Time stop was called
    #   3. Notes
    empty = {'current': 'default', 'sheets': {'default': []}}
    try:
        f = file(filename)
    except IOError, e:
        if e.errno != 2:
            raise
        return empty
    try:
        return pickle.loads(f.read())
    except EOFError:
        return empty
    finally:
        f.close()

def save(filename, ts):
    if not os.path.exists(os.path.basename(filename)):
        for d in subdirs(filename):
            if not os.path.exists(d):
                os.mkdir(d)
    pickled = pickle.dumps(ts, -1)
    f = file(filename, 'w')
    try:
        f.write(pickled)
    finally:
        f.close()

def isactive(sheet):
    return sheet and sheet[-1][1] is None

def running(sheet):
    if isactive(sheet):
        diff = int(time.time()) - sheet[-1][0]
        return str(timedelta(seconds=diff))
    raise ValueError('sheet not active')

def total(sheet):
    return sum([end - start for (start, end, notes) in sheet
               if end is not None]) + (int(time.time()) - sheet[-1][0]
                                       if isactive(sheet) else 0)

def today_total(sheet):
    from bisect import bisect

    now = datetime.now()
    midnight = int(time.mktime(datetime(now.year, now.month,
                                        now.day).timetuple()))
    today = sheet[bisect([r[0] for r in sheet], midnight):]
    return total(today)

@command('display the name of the current timesheet')
def current(ts, options, args):
    parser = OptionParser(usage='''usage: %prog current

Print the name of the current spreadsheet.''')
    opts, args = parser.parse_args(args=args)
    print ts['current']

@command('briefly describe the status of the timesheet')
def info(ts, options, args):
    parser = OptionParser(usage='''usage: %prog status [TIMESHEET]

Print the current sheet, whether it's active, and if so, how long it has
been active and what notes are associated with the current period.

If a specific timesheet is given, display the same information for that
timesheet instaed.''')
    opts, args = parser.parse_args(args=args)
    if args:
        sheet_name, sheet = complete(ts['sheets'], args[0], 'timesheet')
    else:
        sheet_name, sheet = ts['current'], ts['sheets'][ts['current']]
    if isactive(sheet):
        active = running(sheet) + \
                 ' (%s)' % sheet[-1][2].rstrip('.') if sheet[-1][2] else ''
    else:
        active = 'not active'
    print '%s: %s' % (sheet_name, active)

@command('show the current timesheet')
def show(ts, options, args):
    parser = OptionParser(usage='''usage: %prog show [TIMESHEET]

Display a given timesheet. If no timesheet is specified, show the
current timesheet.''')
    opts, args = parser.parse_args(args=args)
    if args:
        sheet_name, sheet = complete(ts['sheets'], args[0], 'timesheet')
    else:
        sheet_name, sheet = ts['current'], ts['sheets'][ts['current']]
    print 'Timesheet %s:' % sheet_name
    if not sheet:
        print '(empty)'
        return

    date = lambda t: datetime.fromtimestamp(t).strftime('%H:%M:%S')
    sheet_total = lambda sheet: str(timedelta(seconds=total(sheet)))
    last_day = None
    day_start = 0
    table = [['Day', 'Start      End', 'Duration', 'Notes']]
    for i, (start, end, notes) in enumerate(sheet):
        day = datetime.fromtimestamp(start).strftime('%b %d, %Y')
        if end is None:
            diff = str(timedelta(seconds=int(time.time()) - start))
            trange = '%s -' % date(start)
        else:
            diff = str(timedelta(seconds=end - start))
            trange = '%s - %s' % (date(start), date(end))
        if last_day == day:
            table.append(['', trange, diff, notes])
        else:
            if last_day is not None:
                day_total = sheet_total(sheet[day_start:i])
                table.append(['', '', day_total, ''])
            table.append([day, trange, diff, notes])
            last_day = day
            day_start = i
    table += [['', '', sheet_total(sheet[day_start:]), ''],
              ['Total', '', sheet_total(sheet), '']]
    pprint_table(table)

@command('start the timer for the current timesheet')
def start(ts, options, args):
    parser = OptionParser(usage='''usage: %prog start [NOTES...]

Start the timer for the current timesheet. Must be called before stop.
Notes may be specified for this period. This is exactly equivalent to
%prog start; %prog write''')
    parser.add_option('-s', '--switch', dest='switch', type='string',
                      help='Switch to another timesheet before starting \
the timer.')
    opts, args = parser.parse_args(args=args)
    now = int(time.time())
    if opts.switch:
        switch(ts, options, [opts.switch])
    sheet = ts['sheets'][ts['current']]
    if isactive(sheet):
        print 'error: timesheet already active'
        raise SystemExit(1)
    sheet.append([now, None, ' '.join(args)])
    save(options.timesheets, ts)

@command('delete a timesheet')
def delete(ts, options, args):
    parser = OptionParser(usage='''usage: %prog delete [TIMESHEET]

Delete a timesheet. If no timesheet is specified, delete the current \
timesheet and switch to the default timesheet.''')
    opts, args = parser.parse_args(args=args)
    if args:
        to_delete = args[0]
    else:
        to_delete = ts['current']
    del ts['sheets'][to_delete]
    if ts['current'] == to_delete:
        switch(ts, options, ['default'])
    else:
        save(options.timesheets, ts)

@command('show the available timesheets')
def list(ts, options, args):
    parser = OptionParser(usage='''usage: %prog list

List the available timesheets.''')
    opts, args = parser.parse_args(args=args)
    table = [[' Timesheet', 'Running', 'Today', 'Total time']]
    for name in sorted(ts['sheets'].keys()):
        sheet = ts['sheets'][name]
        cur_name = '%s%s' % ('*' if name == ts['current'] else ' ', name)
        active = '%s' % running(sheet) \
                 if isactive(sheet) else '--'
        today = str(timedelta(seconds=today_total(sheet)))
        total_time = str(timedelta(seconds=total(sheet)))
        table.append([cur_name, active, today, total_time])
    pprint_table(table)

@command('switch to a new timesheet')
def switch(ts, options, args):
    parser = OptionParser(usage='''usage: %prog switch TIMESHEET

Switch to a new timesheet. This causes all future operation (except switch)
to operate on that timesheet. The default timesheet is called \
"default".''')
    opts, args = parser.parse_args(args=args)
    if len(args) != 1:
        parser.error('no timesheet given')
    ts['current'] = args[0]
    if ts['sheets'].get(ts['current']) is None:
        ts['sheets'][ts['current']] = []
    save(options.timesheets, ts)

@command('stop the timer for the current timesheet')
def stop(ts, options, args):
    parser = OptionParser(usage='''usage: %prog start

Stop the timer for the current timesheet. Must be called after start.''')
    parser.add_option('-v', '--verbose', dest='verbose',
                      action='store_true', help='Show the duration of the \
period that the stop command ends.')
    opts, args = parser.parse_args(args=args)
    now = int(time.time())
    sheet = ts['sheets'][ts['current']]
    if not isactive(sheet):
        print 'error: timesheet not active'
        raise SystemExit(1)
    if opts.verbose:
        print running(sheet)
    sheet[-1][1] = now
    save(options.timesheets, ts)

@command('insert a note into the timesheet')
def write(ts, options, args):
    parser = OptionParser(usage='''usage: %prog write NOTES...

Inserts a note associated with the currently active period in the \
timesheet.''')
    opts, args = parser.parse_args(args=args)

    sheet = ts['sheets'][ts['current']]
    if not isactive(sheet):
        print 'error: timesheet not active'
        raise SystemExit(1)
    sheet[-1][2] = ' '.join(args)
    save(options.timesheets, ts)

@command('edit the timesheets data file')
def edit(ts, options, args):
    from subprocess import call
    from tempfile import mktemp

    parser = OptionParser(usage='''usage: %prog edit

Edit the Python data structures comprising the timesheets data file. No
locking is done, so saving will overwrite any modifications while editing.

Keep the timesheet sorted so that list and show work correctly.''')
    opts, args = parser.parse_args(args=args)

    filename = mktemp()
    f = file(filename, 'w')
    try:
        f.write(pformat_timesheet(options.timesheets))
    finally:
        f.close()
    statbuf = os.stat(filename)

    editor = os.environ.get('EDITOR', 'vi')
    call(editor.split() + [filename])
    if statbuf == os.stat(filename):
        print 'timesheets not modified.'
        os.unlink(filename)
        return

    f = file(filename)
    try:
        ts = eval(f.read())
    finally:
        f.close()
    os.unlink(filename)
    save(options.timesheets, ts)

@command('dump the timesheets data file')
def dump(ts, options, args):
    parser = OptionParser(usage='''usage: %prog dump

Show the unpickled data file.''')
    opts, args = parser.parse_args(args=args)
    print pformat_timesheet(options.timesheets)

def parse_options():
    from optparse import OptionParser
    cmd_descs = ['%s - %s' % (k, commands[k][1])
                 for k in sorted(commands.keys())]
    parser = OptionParser(usage='''usage: %%prog [OPTIONS] COMMAND \
[ARGS...]

where COMMAND is one of:
    %s''' % '\n    '.join(cmd_descs))
    parser.disable_interspersed_args()
    parser.add_option('-d', '--timesheets', dest='timesheets',
                      default=DEFAULTS['timesheets'], help='Specify an \
alternate timesheet file (default: %r).' % DEFAULTS['timesheets'])
    options, args = parser.parse_args()
    if len(args) < 1:
        parser.error('no command specified')
    cmd = complete(commands, args[0], 'command')[1][0]
    return cmd, options, args

def main():
    cmd, options, args = parse_options()
    ts = load(options.timesheets)
    cmd(ts, options, args[1:])

if __name__ == '__main__':
    main()
