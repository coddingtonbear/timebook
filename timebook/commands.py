# commands.py
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

from datetime import datetime, timedelta
from functools import wraps
from gettext import ngettext
from optparse import OptionParser
import os
import subprocess
import sys
import time

from timebook import dbutil, cmdutil

commands = {}
cmd_aliases = {}

def pre_hook(db, func_name):
    if db.config.has_section('hooks'):
        hook = db.config['hooks'].get(func_name)
        if hook is not None:
            __import__(hook, {}, {}, [])
            mod = sys.modules[hook]
            if hasattr(mod, 'pre'):
                return mod.pre
    return lambda db, args, kwargs: (args, kwargs)

def post_hook(db, func_name):
    if db.config.has_section('hooks'):
        hook = db.config['hooks'].get(func_name)
        if hook is not None:
            __import__(hook, {}, {}, [])
            mod = sys.modules[hook]
            if hasattr(mod, 'post'):
                return mod.post
    return lambda db, res: res

def command(desc, name=None, aliases=()):
    def decorator(func):
        func_name = name or func.func_code.co_name
        commands[func_name] = func
        func.description = desc
        for alias in aliases:
            cmd_aliases[alias] = func_name
        @wraps(func)
        def decorated(db, args, **kwargs):
            args, kwargs = pre_hook(db, func_name)(db, args, kwargs)
            res = func(db, args, **kwargs)
            return post_hook(db, func_name)(db, res)
        return decorated
    return decorator

def run_command(db, cmd, args):
    func = cmd_aliases.get(cmd, None)
    if func is None:
        func = cmdutil.complete(commands, cmd, 'command')
    try:
        db.execute(u'begin')
        commands[func](db, args)
    except:
        db.execute(u'rollback')
        raise
    else:
        db.execute(u'commit')

# Commands

@command("open the backend's interactive shell", aliases=('shell',))
def backend(db, args):
    parser = OptionParser(usage='''usage: %prog backend

Run an interactive database session on the timebook database. Requires
the sqlite3 command.''')
    subprocess.call(('sqlite3', db.path))

@command('start the timer for the current timesheet', name='in',
         aliases=('start',))
def in_(db, args, extra=None):
    parser = OptionParser(usage='''usage: %prog in [NOTES...]

Start the timer for the current timesheet. Must be called before out.
Notes may be specified for this period. This is exactly equivalent to
%prog in; %prog alter''')
    parser.add_option('-s', '--switch', dest='switch', type='string',
                      help='Switch to another timesheet before \
starting the timer.')
    parser.add_option('-o', '--out', dest='out', action='store_true',
                      default=False, help='''Clocks out before clocking \
in''')
    parser.add_option('-a', '--at', dest='at', type='string',
                      help='''Set time of clock-in''')
    parser.add_option('-r', '--resume', dest='resume', action='store_true',
                      default=False, help='''Clocks in with status of \
last active period''')
    opts, args = parser.parse_args(args=args)
    if opts.switch:
        sheet = opts.switch
        switch(db, [sheet])
    else:
        sheet = dbutil.get_current_sheet(db)
    timestamp = cmdutil.parse_date_time_or_now(opts.at)
    if opts.out:
        clock_out(db, timestamp=timestamp)
    running = dbutil.get_active_info(db, sheet)
    if running is not None:
        raise SystemExit, 'error: timesheet already active'
    most_recent_clockout = dbutil.get_most_recent_clockout(db, sheet)
    description = u' '.join(args) or None
    if most_recent_clockout:
        (previous_timestamp, previous_description) = most_recent_clockout
        if timestamp < previous_timestamp:
            raise SystemExit, \
                  'error: time periods could end up overlapping'
        if opts.resume:
            description = previous_description
    db.execute(u'''
    insert into entry (
        sheet, start_time, description, extra
    ) values (?,?,?,?)
    ''', (sheet, timestamp, description, extra))

@command('delete a timesheet', aliases=('delete',))
def kill(db, args):
    parser = OptionParser(usage='''usage: %prog kill [TIMESHEET]

Delete a timesheet. If no timesheet is specified, delete the current
timesheet and switch to the default timesheet.''')
    opts, args = parser.parse_args(args=args)
    current = dbutil.get_current_sheet(db)
    if args:
        to_delete = args[0]
        switch_to_default = False
    else:
        to_delete = current
        switch_to_default = True
    try:
        yes_answers = ('y', 'yes')
        # Use print to display the prompt since it intelligently decodes
        # unicode strings.
        print (u'delete timesheet %s?' % to_delete),
        confirm = raw_input('').strip().lower() in yes_answers
    except (KeyboardInterrupt, EOFError):
        confirm = False
        print
    if not confirm:
        print 'canceled'
        return
    db.execute(u'delete from entry where sheet = ?', (to_delete,))
    if switch_to_default:
        switch(db, ['default'])

@command('show the available timesheets', aliases=('ls',))
def list(db, args):
    parser = OptionParser(usage='''usage: %prog list

List the available timesheets.''')
    parser.add_option('-s', '--simple', dest='simple',
                      action='store_true', help='Only display the names \
of the available timesheets.')
    opts, args = parser.parse_args(args=args)

    if opts.simple:
        db.execute(
        u'''
        select
            distinct sheet
        from
            entry
        order by
            sheet asc;
        ''')
        print u'\n'.join(r[0] for r in db.fetchall())
        return

    table = [[' Timesheet', 'Running', 'Today', 'Total time']]
    db.execute(u'''
    select
        e1.sheet as name,
        e1.sheet = meta.value as is_current,
        ifnull((select
            strftime('%s', 'now') - e2.start_time
         from
            entry e2
         where
            e1.sheet = e2.sheet and e2.end_time is null), 0
        ) as active,
        (select
            ifnull(sum(ifnull(e3.end_time, strftime('%s', 'now')) -
                       e3.start_time), 0)
            from
                entry e3
            where
                e1.sheet = e3.sheet and
                e3.start_time > strftime('%s', date('now'))
        ) as today,
        ifnull(sum(ifnull(e1.end_time, strftime('%s', 'now')) -
                   e1.start_time), 0) as total
    from
        entry e1, meta
    where
        meta.key = 'current_sheet'
    group by e1.sheet
    order by e1.sheet asc;
    ''')
    sheets = db.fetchall()
    if len(sheets) == 0:
        print u'(no sheets)'
        return
    for (name, is_current, active, today, total) in sheets:
        cur_name = '%s%s' % ('*' if is_current else ' ', name)
        active = str(timedelta(seconds=active)) if active != 0 \
                                                else '--'
        today = str(timedelta(seconds=today))
        total_time = str(timedelta(seconds=total))
        table.append([cur_name, active, today, total_time])
    cmdutil.pprint_table(table)

@command('switch to a new timesheet')
def switch(db, args):
    parser = OptionParser(usage='''usage: %prog switch TIMESHEET

Switch to a new timesheet. This causes all future operation (except switch)
to operate on that timesheet. The default timesheet is called
"default".''')
    parser.add_option('-v', '--verbose', dest='verbose',
                      action='store_true', help='Print the name and \
number of entries of the timesheet.')
    opts, args = parser.parse_args(args=args)
    if len(args) != 1:
        parser.error('no timesheet given')

    sheet = args[0]

    # optimization: check that the given timesheet is not already
    # current. updates are far slower than selects.
    if dbutil.get_current_sheet(db) != sheet:
        db.execute(u'''
        update
            meta
        set
            value = ?
        where
            key = 'current_sheet'
        ''', (args[0],))

    if opts.verbose:
        entry_count = dbutil.get_entry_count(db, sheet)
        if entry_count == 0:
            print u'switched to empty timesheet "%s"' % sheet
        else:
            print ngettext(
                u'switched to timesheet "%s" (1 entry)' % sheet,
                u'switched to timesheet "%s" (%s entries)' % (
                    sheet, entry_count), entry_count)

@command('stop the timer for the current timesheet', aliases=('stop',))
def out(db, args):
    parser = OptionParser(usage='''usage: %prog out

Stop the timer for the current timesheet. Must be called after in.''')
    parser.add_option('-v', '--verbose', dest='verbose',
                      action='store_true', help='Show the duration of \
the period that the out command ends.')
    parser.add_option('-a', '--at', dest='at',
                      help='Set time of clock-out')
    opts, args = parser.parse_args(args=args)
    clock_out(db, opts.at, opts.verbose)

def clock_out(db, at=None, verbose=False, timestamp=None):
    if not timestamp:
        timestamp = cmdutil.parse_date_time_or_now(at)
    active = dbutil.get_current_start_time(db)
    if active is None:
        raise SystemExit, 'error: timesheet not active'
    active_id, start_time = active
    active_time = timestamp - start_time
    if verbose:
        print timedelta(seconds=active_time)
    if active_time < 0:
        raise SystemExit, "Error: Negative active time"
    db.execute(u'''
    update
        entry
    set
        end_time = ?
    where
        entry.id = ?
    ''', (timestamp, active_id))

@command('alter the description of the active period', aliases=('write',))
def alter(db, args):
    parser = OptionParser(usage='''usage: %prog alter NOTES...

Inserts a note associated with the currently active period in the \
timesheet. For example, ``t alter Documenting timebook.``''')
    opts, args = parser.parse_args(args=args)

    active = dbutil.get_current_active_info(db)
    if active is None:
        raise SystemExit, 'error: timesheet not active'
    entry_id = active[0]
    db.execute(u'''
    update
        entry
    set
        description = ?
    where
        entry.id = ?
    ''', (' '.join(args), entry_id))

@command('show all running timesheets', aliases=('active',))
def running(db, args):
    parser = OptionParser(usage='''usage: %prog running

Print all active sheets and any messages associated with them.''')
    opts, args = parser.parse_args(args=args)
    db.execute(u'''
    select
        entry.sheet,
        ifnull(entry.description, '--')
    from
        entry
    where
        entry.end_time is null
    order by
        entry.sheet asc;
    ''')
    cmdutil.pprint_table([(u'Timesheet', u'Description')] + db.fetchall())

@command('show the status of the current timesheet',
         aliases=('info',))
def now(db, args):
    parser = OptionParser(usage='''usage: %prog now [TIMESHEET]

Print the current sheet, whether it's active, and if so, how long it
has been active and what notes are associated with the current
period.

If a specific timesheet is given, display the same information for that
timesheet instead.''')
    parser.add_option('-s', '--simple', dest='simple',
                      action='store_true', help='Only display the name \
of the current timesheet.')
    parser.add_option('-n', '--notes', dest='notes',
                      action='store_true', help='Only display the notes \
associated with the current period.')
    opts, args = parser.parse_args(args=args)

    if opts.simple:
        print dbutil.get_current_sheet(db)
        return

    if args:
        sheet = cmdutil.complete(dbutil.get_sheet_names(db), args[0],
                                 'timesheet')
    else:
        sheet = dbutil.get_current_sheet(db)

    entry_count = dbutil.get_entry_count(db, sheet)
    if entry_count == 0:
        raise SystemExit, '%(prog)s: error: sheet is empty. For program \
usage, see "%(prog)s --help".' % {'prog': os.path.basename(sys.argv[0])}

    running = dbutil.get_active_info(db, sheet)
    notes = ''
    if running is None:
        active = 'not active'
    else:
        duration = str(timedelta(seconds=running[0]))
        if running[1]:
            notes = running[1].rstrip('.')
            active = '%s (%s)' % (duration, notes)
        else:
            active = duration
    if opts.notes:
        print notes
    else:
        print '%s: %s' % (sheet, active)

@command('display timesheet, by default the current one',
         aliases=('export', 'format', 'show'))
def display(db, args):
    # arguments
    parser = OptionParser(usage='''usage: %prog display [TIMESHEET]

Display the data from a timesheet in the range of dates specified, either
in the normal timebook fashion (using --format=plain) or as
comma-separated value format spreadsheet (using --format=csv), which
ignores the final entry if active.

If a specific timesheet is given, display the same information for that
timesheet instead.''')
    parser.add_option('-s', '--start', dest='start', type='string',
                      metavar='DATE', help='Show only entries \
starting after 00:00 on this date. The date should be of the format \
YYYY-MM-DD.')
    parser.add_option('-e', '--end', dest='end', type='string',
                      metavar='DATE', help='Show only entries \
ending before 00:00 on this date. The date should be of the format \
YYYY-MM-DD.')
    parser.add_option('-f', '--format', dest='format', type='string',
                  default='plain',
                  help="Select whether to output in the normal timebook \
style (--format=plain) or csv --format=csv")
    opts, args = parser.parse_args(args=args)

    # grab correct sheet
    if args:
        sheet = cmdutil.complete(dbutil.get_sheet_names(db), args[0],
                                 'timesheet')
    else:
        sheet = dbutil.get_current_sheet(db)

    #calculate "where"
    where = ''
    fmt = '%Y-%m-%d'
    if opts.start is not None:
        start = cmdutil.parse_date_time(opts.start)
        where += ' and start_time >= %s' % start
    if opts.end is not None:
        end = cmdutil.parse_date_time(opts.end)
        where += ' and end_time <= %s' % end
    if opts.format == 'plain':
        format_timebook(db, sheet, where)
    elif opts.format == 'csv':
        format_csv(db, sheet, where)
    else:
        raise SystemExit, 'Invalid format: %s' % opts.format

def format_csv(db, sheet, where):
    import csv

    writer = csv.writer(sys.stdout)
    writer.writerow(('Start', 'End', 'Length', 'Description'))
    db.execute(u'''
    select
       start_time,
       end_time,
       ifnull(end_time, strftime('%%s', 'now')) -
           start_time,
       description
    from
       entry
    where
       sheet = ? and
       end_time is not null%s
    ''' % where, (sheet,))
    format = lambda t: datetime.fromtimestamp(t).strftime(
        '%m/%d/%Y %H:%M:%S')
    rows = db.fetchall()
    writer.writerows(map(lambda row: (
        format(row[0]), format(row[1]), row[2], row[3]), rows))
    total_formula = '=SUM(C2:C%d)/3600' % (len(rows) + 1)
    writer.writerow(('Total', '', total_formula, ''))

def format_timebook(db, sheet, where):
    db.execute(u'''
    select count(*) > 0 from entry where sheet = ?%s
    ''' % where, (sheet,))
    if not db.fetchone()[0]:
        print '(empty)'
        return

    displ_time = lambda t: time.strftime('%H:%M:%S', time.localtime(t))
    displ_date = lambda t: time.strftime('%b %d, %Y',
                                         time.localtime(t))
    displ_total = lambda t: \
            cmdutil.timedelta_hms_display(timedelta(seconds=t))

    last_day = None
    table = [['Day', 'Start      End', 'Duration', 'Notes']]
    db.execute(u'''
    select
        date(e.start_time, 'unixepoch', 'localtime') as day,
        ifnull(sum(ifnull(e.end_time, strftime('%%s', 'now')) -
                   e.start_time), 0) as day_total
    from
        entry e
    where
        e.sheet = ?%s
    group by
        day
    order by
        day asc;
    ''' % where, (sheet,))
    days = db.fetchall()
    days_iter = iter(days)
    db.execute(u'''
    select
        date(e.start_time, 'unixepoch', 'localtime') as day,
        e.start_time as start,
        e.end_time as end,
        ifnull(e.end_time, strftime('%%s', 'now')) - e.start_time as
            duration,
        ifnull(e.description, '') as description
    from
        entry e
    where
        e.sheet = ?%s
    order by
        day asc;
    ''' % where, (sheet,))
    entries = db.fetchall()
    for i, (day, start, end, duration, description) in \
            enumerate(entries):
        date = displ_date(start)
        diff = displ_total(duration)
        if end is None:
            trange = '%s -' % displ_time(start)
        else:
            trange = '%s - %s' % (displ_time(start), displ_time(end))
        if last_day == day:
            # If this row doesn't represent the first entry of the
            # day, don't display anything in the day column.
            table.append(['', trange, diff, description])
        else:
            if last_day is not None:
                # Use day_total set (below) from the previous
                # iteration. This is skipped the first iteration,
                # since last_day is None.
                table.append(['', '', displ_total(day_total), ''])
            cur_day, day_total = days_iter.next()
            assert day == cur_day
            table.append([date, trange, diff, description])
            last_day = day

    db.execute(u'''
    select
        ifnull(sum(ifnull(e.end_time, strftime('%%s', 'now')) -
                   e.start_time), 0) as total
    from
        entry e
    where
        e.sheet = ?%s;
    ''' % where, (sheet,))
    total = displ_total(db.fetchone()[0])
    table += [['', '', displ_total(day_total), ''],
              ['Total', '', total, '']]
    cmdutil.pprint_table(table, footer_row=True)
