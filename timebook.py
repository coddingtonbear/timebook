#!/usr/bin/python
#
# timebook 0.3.0 Copyright (c) 2008-2009 Trevor Caira
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

__author__ = 'Trevor Caira <trevor@caira.com>'
__version__ = (0, 3, 0)

from ConfigParser import SafeConfigParser
from datetime import datetime, timedelta
from functools import wraps
from optparse import OptionParser
import os
import sqlite3
import sys
import time

confdir = os.path.expanduser(os.path.join('~', '.config', 'timebook'))
DEFAULTS = {'config': os.path.join(confdir, 'timebook.ini'),
            'timebook': os.path.join(confdir, 'sheets.db')}

class AmbiguousLookup(ValueError): pass

class ConfigParser(SafeConfigParser):
    def __getitem__(self, name):
        return dict(self.items(name))

class NoMatch(ValueError): pass

commands = {}
aliases = {}
def command(desc, cmd_aliases=()):
    def decorator(func):
        func_name = func.func_code.co_name
        commands[func_name] = desc
        for alias in cmd_aliases:
            aliases[alias] = func
        def decorated(self, args, **kwargs):
            args, kwargs = self.pre_hook(func_name)(self, args, kwargs)
            res = func(self, args, **kwargs)
            return self.post_hook(func_name)(self, res)
        return wraps(func)(decorated)
    return decorator

class Timebook(dict):
    def __init__(self, options, config):
        self.options = options
        self.config = config
        self.db = sqlite3.connect(options.timebook, isolation_level=None)
        self.cursor = self.db.cursor()
        for attr in ('execute', 'fetchone', 'fetchall'):
            setattr(self, attr, getattr(self.cursor, attr))
        self._create_db()

    def _create_db(self):
        self.cursor.executescript(u'''
        begin;
        create table if not exists meta (
            key varchar(16) primary key not null,
            value varchar(32) not null
        );
        create table if not exists entry (
            id integer primary key not null,
            sheet varchar(32) not null,
            start_time integer not null,
            end_time integer,
            description varchar(64),
            extra blob
        );
        create index if not exists entry_sheet on entry (sheet);
        create index if not exists entry_start_time on entry (start_time);
        create index if not exists entry_end_time on entry (end_time);
        ''')
        self.execute(u'''
        select
            count(*)
        from
            meta
        where
            key = 'current_sheet'
        ''')
        count = self.fetchone()[0]
        if count == 0:
            self.execute(u'''
            insert into meta (
                key, value 
            ) values (
                'current_sheet', 'default'
            )''')
        # TODO: version
        self.execute(u'commit')

    @property
    def current_sheet(self):
        self.execute(u'''
        select
            value
        from
            meta
        where
            key = 'current_sheet'
        ''')
        return self.fetchone()[0]

    def get_sheet_names(self):
        self.execute(u'''
        select
            distinct sheet
        from
            entry
        ''')
        return tuple(r[0] for r in self.fetchall())

    def get_active_info(self, sheet):
        self.execute(u'''
        select
            strftime('%s', 'now') - entry.start_time,
            entry.description
        from
            entry
        where
            entry.sheet = ? and
            entry.end_time is null
        ''', (sheet,))
        return self.fetchone()

    def get_current_active_info(self):
        self.execute(u'''
        select
            entry.id,
            strftime('%s', 'now') - entry.start_time
        from
            entry
        inner join
            meta
        on
            meta.key = 'current_sheet' and
            meta.value = entry.sheet
        where
            entry.end_time is null
        ''')
        return self.fetchone()

    def pre_hook(self, func_name):
        if self.config.has_section('hooks'):
            hook = self.config['hooks'].get(func_name)
            if hook is not None:
                __import__(hook, {}, {}, [])
                mod = sys.modules[hook]
                if hasattr(mod, 'pre'):
                    return mod.pre
        return lambda self, args, kwargs: (args, kwargs)

    def post_hook(self, func_name):
        if self.config.has_section('hooks'):
            hook = self.config['hooks'].get(func_name)
            if hook is not None:
                __import__(hook, {}, {}, [])
                mod = sys.modules[hook]
                if hasattr(mod, 'post'):
                    return mod.post
        return lambda self, res: res

    def run_command(self, cmd, args):
        func = aliases.get(cmd, None)
        if func is None:
            func = complete(commands, cmd, 'command')
        self.execute(u'begin')
        getattr(self, func)(args)
        self.execute(u'commit')

    @command('open an interactive database shell')
    def shell(self, args):
        parser = OptionParser(usage='''usage: %prog dump

Run an interactive database session on the timebook database. Requires
the sqlite3 command.''')
        os.execvp('sqlite3', ('sqlite3', self.options.timebook))

    @command('show the current timesheet')
    def show(self, args):
        parser = OptionParser(usage='''usage: %prog show [TIMESHEET]

Display a given timesheet. If no timesheet is specified, show the
current timesheet.''')
        opts, args = parser.parse_args(args=args)
        if args:
            sheet = complete(self.get_sheet_names(), args[0], 'timesheet')
        else:
            sheet = self.current_sheet
        print 'Timesheet %s:' % sheet
        self.execute(u'''
        select count(*) > 0 from entry where sheet = ?
        ''', (sheet,))
        if not self.fetchone()[0]:
            print '(empty)'
            return

        displ_time = lambda t: time.strftime('%H:%M:%S', time.localtime(t))
        displ_date = lambda t: time.strftime('%b %d, %Y',
                                             time.localtime(t))
        displ_total = lambda t: str(timedelta(seconds=t))
        last_day = None
        table = [['Day', 'Start      End', 'Duration', 'Notes']]
        self.execute(u'''
        select
            date(e.start_time, 'unixepoch', 'localtime') as day,
            ifnull(sum(ifnull(e.end_time, strftime('%s', 'now')) -
                       e.start_time), 0) as day_total
        from
            entry e
        where
            e.sheet = ?
        group by
            day
        order by
            day asc;
        ''', (sheet,))
        days = self.fetchall()
        days_iter = iter(days)
        self.execute(u'''
        select
            date(e.start_time, 'unixepoch', 'localtime') as day,
            e.start_time as start,
            e.end_time as end,
            ifnull(e.end_time, strftime('%s', 'now')) - e.start_time as
                duration,
            ifnull(e.description, '') as description
        from
            entry e
        where
            e.sheet = ?
        order by
            day asc;
        ''', (sheet,))
        entries = self.fetchall()
        for i, (day, start, end, duration, description) in \
                enumerate(entries):
            date = displ_date(start)
            diff = displ_total(duration)
            if end is None:
                trange = '%s -' % displ_time(start)
            else:
                trange = '%s - %s' % (displ_time(start), displ_time(end))
            if last_day == day:
                # If this row doesn't represent the first entry fo the
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

        self.execute(u'''
        select
            ifnull(sum(ifnull(e.end_time, strftime('%s', 'now')) -
                       e.start_time), 0) as total
        from
            entry e
        where
            e.sheet = ?;
        ''', (sheet,))
        total = displ_total(self.fetchone()[0])
        table += [['', '', displ_total(day_total), ''],
                  ['Total', '', total, '']]
        pprint_table(table, footer_row=True)

    @command('start the timer for the current timesheet')
    def start(self, args, extra=None):
        parser = OptionParser(usage='''usage: %prog start [NOTES...]

Start the timer for the current timesheet. Must be called before stop.
Notes may be specified for this period. This is exactly equivalent to
%prog start; %prog write''')
        parser.add_option('-s', '--switch', dest='switch', type='string',
                          help='Switch to another timesheet before \
starting the timer.')
        opts, args = parser.parse_args(args=args)
        now = int(time.time())
        if opts.switch:
            sheet = opts.switch
            self.switch([sheet])
        else:
            sheet = self.current_sheet
        running = self.get_active_info(sheet)
        if running is not None:
            raise SystemExit, 'error: timesheet already active'
        description = u' '.join(args) or None
        self.execute(u'''
        insert into entry (
            sheet, start_time, description, extra
        ) values (?,?,?,?)
        ''', (sheet, now, description, extra))

    @command('delete a timesheet')
    def delete(self, args):
        parser = OptionParser(usage='''usage: %prog delete [TIMESHEET]

Delete a timesheet. If no timesheet is specified, delete the current \
timesheet and switch to the default timesheet.''')
        opts, args = parser.parse_args(args=args)
        current = self.current_sheet
        if args:
            to_delete = args[0]
            switch_to_default = False
        else:
            to_delete = current
            switch_to_default = True
        try:
            yes_answers = ('y', 'yes')
            prompt = 'delete timebook %s? ' % to_delete
            confirm = raw_input(prompt).strip().lower() in yes_answers
        except (KeyboardInterrupt, EOFError):
            confirm = False
            print
        if not confirm:
            print 'canceled'
            return
        self.execute(u'delete from entry where sheet = ?', (to_delete,))
        if switch_to_default:
            self.switch(['default'])

    @command('show the available timesheets')
    def list(self, args):
        parser = OptionParser(usage='''usage: %prog list

List the available timesheets.''')
        opts, args = parser.parse_args(args=args)
        table = [[' Timesheet', 'Running', 'Today', 'Total time']]
        self.execute(u'''
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
        sheets = self.fetchall()
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
        pprint_table(table)

    @command('switch to a new timesheet')
    def switch(self, args):
        parser = OptionParser(usage='''usage: %prog switch TIMESHEET

Switch to a new timesheet. This causes all future operation (except switch)
to operate on that timesheet. The default timesheet is called
"default".''')
        opts, args = parser.parse_args(args=args)
        if len(args) != 1:
            parser.error('no timesheet given')
        self.execute(u'''
        update
            meta
        set
            value = ?
        where
            key = 'current_sheet'
        ''', (args[0],))

    @command('stop the timer for the current timesheet')
    def stop(self, args):
        parser = OptionParser(usage='''usage: %prog stop

Stop the timer for the current timesheet. Must be called after start.''')
        parser.add_option('-v', '--verbose', dest='verbose',
                          action='store_true', help='Show the duration of \
the period that the stop command ends.')
        opts, args = parser.parse_args(args=args)
        now = int(time.time())
        active = self.get_current_active_info()
        if active is None:
            raise SystemExit, 'error: timesheet not active'
        active_id, active_time = active
        if opts.verbose:
            print timedelta(seconds=active_time)
        self.execute(u'''
        update
            entry
        set
            end_time = ?
        where
            entry.id = ?
        ''', (now, active_id))

    @command('insert a note into the timesheet')
    def write(self, args):
        parser = OptionParser(usage='''usage: %prog write NOTES...

Inserts a note associated with the currently active period in the \
timesheet.''')
        opts, args = parser.parse_args(args=args)

        active = self.get_current_active_info()
        if active is None:
            raise SystemExit, 'error: timesheet not active'
        entry_id = active[0]
        self.execute(u'''
        update
            entry
        set
            description = ?
        where
            entry.id = ?
        ''', (' '.join(args), entry_id))

    @command('display the name of the current timesheet')
    def current(self, args):
        parser = OptionParser(usage='''usage: %prog current

Print the name of the current spreadsheet.''')
        opts, args = parser.parse_args(args=args)
        print self.current_sheet

    @command('show all active timesheets')
    def active(self, args):
        parser = OptionParser(usage='''usage: %prog active

Print all active sheets and any messages associated with them.''')
        opts, args = parser.parse_args(args=args)
        self.execute(u'''
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
        pprint_table([(u'Timesheet', u'Description')] + self.fetchall())

    @command('briefly describe the status of the timesheet')
    def info(self, args):
        parser = OptionParser(usage='''usage: %prog info [TIMESHEET]

Print the current sheet, whether it's active, and if so, how long it
has been active and what notes are associated with the current
period.

If a specific timesheet is given, display the same information for that
timesheet instead.''')
        opts, args = parser.parse_args(args=args)
        if args:
            sheet = complete(self.get_sheet_names(), args[0], 'timesheet')
        else:
            sheet = self.current_sheet
        running = self.get_active_info(sheet)
        if running is None:
            active = 'not active'
        else:
            duration = str(timedelta(seconds=running[0]))
            if running[1]:
                active = '%s (%s)' % (duration, running[1].rstrip('.'))
            else:
                active = duration
        print '%s: %s' % (sheet, active)

    @command('export a sheet to csv format')
    def csv(self, args):
        from bisect import bisect
        import csv

        parser = OptionParser(usage='''usage: %prog csv [TIMESHEET]

Export the current sheet as a comma-separated value format spreadsheet.
If the final entry is active, it is ignored.

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
        opts, args = parser.parse_args(args=args)
        if args:
            sheet = complete(self.get_sheet_names(), args[0], 'timesheet')
        else:
            sheet = self.current_sheet
        fmt = '%Y-%m-%d'
        where = ''
        if opts.start is not None:
            start_date = datetime.strptime(opts.start, fmt)
            start = datetime_to_int(start_date)
            where += ' and start_time >= %s' % start
        if opts.end is not None:
            end_date = datetime.strptime(opts.end, fmt)
            end = datetime_to_int(end_date)
            where += ' and end_time <= %s' % end
        writer = csv.writer(sys.stdout)
        writer.writerow(('Start', 'End', 'Length', 'Description'))
        self.execute(u'''
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
        writer.writerows(map(lambda row: (
            format(row[0]), format(row[1]), row[2], row[3]),
            self.fetchall()))
        total_formula = '=SUM(C2:C%d)/3600' % (len(sheet) + 1)
        writer.writerow(('Total', '', total_formula, ''))

def complete(it, lookup, key_desc):
    partial_match = None
    for i in it:
        if i == lookup:
            return i
        if i.startswith(lookup):
            if partial_match is not None:
                matches = sorted(i for i in it if i.startswith(lookup))
                raise AmbiguousLookup('ambiguous %s %r:' %
                                      (key_desc, lookup), matches)
            partial_match = i
    if partial_match is None:
        raise NoMatch('no such %s %r.' % (key_desc, lookup))
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

def parse_options():
    from optparse import OptionParser
    cmd_descs = ['%s - %s' % (k, commands[k])
                 for k in sorted(commands.keys())]
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

def parse_config(filename):
    config = ConfigParser()
    f = open(filename)
    try:
        config.readfp(f)
    finally:
        f.close()
    return config

def cmdline():
    options, args = parse_options()
    config = parse_config(options.config)
    book = Timebook(options, config)
    cmd, args = args[0], args[1:]
    try:
        book.run_command(cmd, args)
    except NoMatch, e:
        raise SystemExit, 'error: %s' % e.args[0]
    except AmbiguousLookup, e:
        raise SystemExit, 'error: %s\n    %s' % (e.args[0],
                                                 ' '.join(e.args[1]))

if __name__ == '__main__':
    cmdline()
