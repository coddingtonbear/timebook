# commands.py
#
# Copyright (c) 2008-2009 Trevor Caira, 2011-2012 Adam Coddington
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
import httplib
import json
import os
import optparse
import re
import shlex
import subprocess
import sys
import time
from urllib import urlencode
from urlparse import urlparse

from timebook import logger, dbutil, cmdutil, exceptions
from timebook.autopost import TimesheetPoster
from timebook.payperiodutil import PayPeriodUtil
from timebook.cmdutil import rawinput_date_format

commands = {}
cmd_aliases = {}


def pre_hook(db, func_name, args, kwargs):
    current_sheet = dbutil.get_current_sheet(db)
    keys_to_check = [
                'pre_%s_hook' % func_name,
                'pre_hook',
            ]
    for key_name in keys_to_check:
        if db.config.has_option(current_sheet, key_name):
            command = shlex.split(
                        db.config.get(current_sheet, key_name),
                    )
            res = subprocess.call(
                    command + args,
                )
            if res != 0:
                raise exceptions.PreHookException(
                        "%s (%s)(%s)" % (command, func_name, ', '.join(args))
                    )
    return True


def post_hook(db, func_name, args, kwargs, res):
    current_sheet = dbutil.get_current_sheet(db)
    keys_to_check = [
                'post_%s_hook' % func_name,
                'post_hook',
            ]
    for key_name in keys_to_check:
        if db.config.has_option(current_sheet, key_name):
            command = shlex.split(
                        db.config.get(current_sheet, key_name),
                    )
            res = subprocess.call(
                    command + args + [str(res)]
                )
            if res != 0:
                raise exceptions.PostHookException(
                        "%s (%s)(%s)(%s)" %
                        (command, func_name, ', '.join(args), res)
                    )
    return True


def command(desc, name=None, aliases=(), locking=True, read_only=True):
    def decorator(func):
        func_name = name or func.func_code.co_name
        commands[func_name] = func
        func.description = desc
        func.locking = locking
        func.read_only = read_only
        for alias in aliases:
            cmd_aliases[alias] = func_name

        @wraps(func)
        def decorated(db, args, **kwargs):
            try:
                pre_hook(db, func_name, args, kwargs)
                res = func(db, args, **kwargs)
                post_hook(db, func_name, args, kwargs, res)
            except exceptions.PreHookException as e:
                print "Error, command aborted. Pre hook failed: %s" % e
                raise e
            except exceptions.PostHookException as e:
                print "Warning. Post hook failed: %s" % e
                raise e
        commands[func_name] = decorated
        return decorated
    return decorator


def get_command_by_user_configured_alias(db, cmd):
    if (
        not db.config.has_section('aliases') 
        or not db.config.has_option('aliases', cmd)
        ):
        return
    alias = db.config.get('aliases', cmd)
    if alias in commands.keys():
        return alias
    else:
        raise exceptions.CommandError("The alias '%s' is mapped to a function that does not exist." % cmd)


def get_command_by_name(db, cmd):
    func = get_command_by_user_configured_alias(db, cmd)
    if func:
        return func
    func = cmd_aliases.get(cmd, None)
    if func:
        return func
    return cmdutil.complete(commands, cmd, 'command')


def run_command(db, cmd, args):
    func = get_command_by_name(db, cmd)
    try:
        if commands[func].locking:
            db.execute(u'begin')
        commands[func](db, args)
        if commands[func].locking:
            db.execute(u'commit')
        current_sheet = dbutil.get_current_sheet(db)
        if not commands[func].read_only:
            if db.config.has_option(
                        current_sheet,
                        'reporting_url'
                    ) and db.config.has_option(
                        'auth',
                        'username'
                    ):
                current_info = dbutil.get_active_info(db, current_sheet)
                report_to_url(
                        db.config.get(current_sheet, 'reporting_url'),
                        db.config.get('auth', 'username'),
                        current_info[1] if current_info else '',
                        (
                            datetime.utcnow()
                            - timedelta(seconds=current_info[0])
                        ).strftime("%Y-%m-%d %H:%M:%S")
                        if current_info else '',
                        cmd,
                        args
                    )
            elif db.config.has_option(current_sheet, 'reporting_url'):
                print "Please specify a username in your configuration."
    except:
        if commands[func].locking:
            db.execute(u'rollback')
        raise


def report_to_url(url, user, current, since, command, args):
    try:
        url_data = urlparse(url)
        h = httplib.HTTPConnection(url_data.netloc)
        h.request("POST", url_data.path, urlencode({
                'user': user,
                'command': command,
                'current': current,
                'since': since,
                'args': json.dumps(args),
            }), {
                "Content-type": "application/x-www-form-urlencoded",
                "Accept": "text/plain"
            })
        response = h.getresponse()
        content = response.read()
        if response.status != 200:
            raise exceptions.ReportingException(
                "HTTP Error %s encountered while posting reporting "
                + "information." % response.status
                )
        if len(content) > 0:
            print content
    except Exception as e:
        print e


def get_date_from_cli_string(option,  option_str, value, parser):
    if(value == 'today'):
        the_date = datetime.now().date()
    elif(value == 'yesterday'):
        the_date = (datetime.now() + timedelta(days=-1)).date()
    elif(re.match("^-\d+$", value)):
        the_date = (datetime.now() + timedelta(days=int(value))).date()
    elif(re.match("^\d{4}-\d{2}-\d{2}$", value)):
        try:
            the_date = datetime.strptime(value, "%Y-%m-%d").date()
        except Exception as e:
            raise optparse.OptionValueError(
                    "'%s' does not match format YYYY-MM-DD" % value
                )
    else:
        raise optparse.OptionValueError("Unrecognized date argument.")
    setattr(parser.values, option.dest, the_date)

# Commands


@command("open the backend's interactive shell", aliases=('shell',), 
        locking=False)
def backend(db, args):
    parser = optparse.OptionParser(usage='''usage: %prog backend

Run an interactive database session on the timebook database. Requires
the sqlite3 command.''')
    subprocess.call(('sqlite3', db.path))


@command('start a new task on the current timesheet', name='change')
def change(db, args, extra=None):
    out(db, [])
    in_(db, args, change=True)


@command('post timesheet hours to timesheet online',
        name='post', locking=False)
def post(db, args, extra=None):
    parser = optparse.OptionParser()
    parser.add_option("--date", type="string", action="callback",
            help='''Date for which to post timesheet entries for.

Must be in either YYYY-MM-DD format, be the string 'yesterday' or 'today',
or be a negative number indicating the number of days ago for which to run
the report.  (default: today)''',
            callback=get_date_from_cli_string,
            dest="date",
            default=datetime.now().date()
        )
    (options, args, ) = parser.parse_args()

    with TimesheetPoster(
            db,
            options.date,
            ) as app:
        try:
            app.main()
        except Exception, e:
            raise e


@command('provides hours information for the current pay period', name='hours',
        aliases=('payperiod', 'pay', 'period', 'offset', ), read_only=True)
def hours(db, args, extra=None):
    payperiod_class = 'MonthlyOnSecondToLastFriday'
    current_sheet = dbutil.get_current_sheet(db)
    if db.config.has_option(current_sheet, 'payperiod_type'):
        payperiod_class = db.config.get(current_sheet, 'payperiod_type')

    parser = optparse.OptionParser()
    parser.add_option("--param", type="string", dest="param", default=None)
    parser.add_option(
        "--payperiod-type", type="string",
        dest="payperiod_type", default=payperiod_class
    )
    (options, args, ) = parser.parse_args()

    ppu = PayPeriodUtil(db, options.payperiod_type)
    hour_info = ppu.get_hours_details()
    if options.param and options.param in hour_info.keys():
        param = hour_info[options.param]
        if isinstance(param, datetime):
            param = int(time.mktime(param.timetuple()))
        print param
    else:
        print "Period: %s through %s" % (
                hour_info['begin_period'].strftime("%Y-%m-%d"),
                hour_info['end_period'].strftime("%Y-%m-%d"),
                )

        if(hour_info['actual'] > hour_info['expected']):
            print "%.2f hour SURPLUS" % (
                    hour_info['actual'] - hour_info['expected'],
                )
            print "%s hours unpaid" % (hour_info['unpaid'],)
            print "%s hours vacation" % (hour_info['vacation'], )
            print ""
            print "You should have left at %s today to maintain hours." % (
                    hour_info['out_time'].strftime("%H:%M"),
                )
        else:
            print "%.2f hour DEFICIT" % (
                    hour_info['expected'] - hour_info['actual']
                )
            print "%s hours unpaid" % (hour_info['unpaid'])
            print "%s hours vacation" % (hour_info['vacation'], )
            print ""
            print "You should leave at %s today to maintain hours." % (
                    hour_info['out_time'].strftime("%H:%M"),
                )


@command('start the timer for the current timesheet', name='in',
         aliases=('start',))
def in_(db, args, extra=None, change=False):
    parser = optparse.OptionParser(usage='''usage: %prog in [NOTES...]

Start the timer for the current timesheet. Must be called before out.
Notes may be specified for this period. This is exactly equivalent to
%prog in; %prog alter''')
    parser.add_option('-s', '--switch', dest='switch', type='string',
            help='Switch to another timesheet before starting the timer.'
            )
    parser.add_option('-o', '--out', dest='out', action='store_true',
            default=False, help='Clocks out before clocking in'
            )
    parser.add_option('-a', '--at', dest='at', type='string',
            help='Set time of clock-in'
            )
    parser.add_option('-t', '--ticket', dest='ticket_number', type='string',
            default=None, help='Set ticket number'
            )
    parser.add_option('--billable', dest='billable', action='store_true',
            default=True, help='Marks entry as billable'
            )
    parser.add_option('--non-billable', dest='billable', action='store_false',
            default=True, help='Marks entry as non-billable'
            )
    cmdutil.add_user_specified_attributes(db, parser)
    opts, args = parser.parse_args(args=args)
    metadata = cmdutil.collect_user_specified_attributes(db, opts)
    metadata['billable'] = 'yes' if opts.billable else 'no'
    if opts.ticket_number:
        metadata['ticket_number'] = opts.ticket_number
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
        raise SystemExit('error: timesheet already active')
    most_recent_clockout = dbutil.get_most_recent_clockout(db, sheet)
    description = u' '.join(args) or None
    if most_recent_clockout:
        (id, start_time, prev_timestamp, prev_desc) = most_recent_clockout
        prev_meta = dbutil.get_entry_meta(db, id)
        if timestamp < prev_timestamp:
            raise SystemExit('error: time periods could end up overlapping')
        current_sheet = dbutil.get_current_sheet(db)
        if change and db.config.has_option(current_sheet, 'autocontinue'):
            if not description:
                description = prev_desc
            for p_key, p_value in prev_meta.items():
                if p_key not in metadata.keys() or not metadata[p_key]:
                    metadata[p_key] = p_value

    db.execute(u'''
    insert into entry (
        sheet, start_time, description, extra
    ) values (?,?,?,?)
    ''', (sheet, timestamp, description, extra))
    entry_id = db.cursor.lastrowid
    dbutil.update_entry_meta(db, entry_id, metadata)


@command('delete a timesheet', aliases=('delete',))
def kill(db, args):
    parser = optparse.OptionParser(usage='''usage: %prog kill [TIMESHEET]

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


@command('show the available timesheets', aliases=('ls',), read_only=True)
def list(db, args):
    parser = optparse.OptionParser(usage='''usage: %prog list

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


@command('switch to a new timesheet', read_only=True)
def switch(db, args):
    parser = optparse.OptionParser(usage='''usage: %prog switch TIMESHEET

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
    parser = optparse.OptionParser(usage='''usage: %prog out

Stop the timer for the current timesheet. Must be called after in.''')
    parser.add_option('-v', '--verbose', dest='verbose',
                      action='store_true', help='Show the duration of \
the period that the out command ends.')
    parser.add_option('-a', '--at', dest='at',
                      help='Set time of clock-out')
    parser.add_option('--all', dest='all_out', action='store_true',
            default=False, help='Clock out of all timesheets')
    opts, args = parser.parse_args(args=args)
    if args:
        parser.error('"t out" takes no arguments.')
    clock_out(db, opts.at, opts.verbose, all_out=opts.all_out)

    try:
        value = db.config.get('automation', 'post_on_clockout')
        if value:
            post(db, [])
    except Exception:
        pass


def clock_out(db, at=None, verbose=False, timestamp=None, all_out=False):
    if not timestamp:
        timestamp = cmdutil.parse_date_time_or_now(at)
    active = dbutil.get_current_start_time(db)
    if active is None:
        raise SystemExit('error: timesheet not active')
    active_id, start_time = active
    active_time = timestamp - start_time
    if verbose:
        print timedelta(seconds=active_time)
    if active_time < 0:
        raise SystemExit("Error: Negative active time")
    if all_out:
        db.execute(u'''
        UPDATE
            entry
        SET
            end_time = ?
        WHERE
            end_time is null
        ''', (timestamp, ))
    else:
        db.execute(u'''
        update
            entry
        set
            end_time = ?
        where
            entry.id = ?
        ''', (timestamp, active_id))


@command('create a new timebook entry and backdate it')
def backdate(db, args):
    try:
        try:
            now_dt = datetime.now()
            offset = cmdutil.get_time_offset(args[0])
            start = datetime(
                now_dt.year,
                now_dt.month,
                now_dt.day,
                now_dt.hour,
                now_dt.minute,
                now_dt.second
            ) - offset
        except ValueError:
            start = datetime.fromtimestamp(cmdutil.parse_date_time(args[0]))
        args = args[1:]

        active = dbutil.get_current_start_time(db)
        if active:
            clock_out(db)

        sql = """
            SELECT id 
            FROM entry
            WHERE 
                sheet = ?
                AND
                end_time > ?
        """
        sql_args = (
            dbutil.get_current_sheet(db),
            int(time.mktime(start.timetuple())),
        )
        db.execute(sql, sql_args)

        rows = db.fetchall()

        if len(rows) > 1:
            raise exceptions.CommandError(
                '%s overlaps %s entries. '
                'Please select a later time to backdate to.' % (
                    start,
                    len(rows)
                )
            )

        sql = """
            UPDATE entry
            SET end_time = ?
            WHERE 
                sheet = ?
                AND
                end_time > ?
        """
        sql_args = (
            int(time.mktime(start.timetuple())),
            dbutil.get_current_sheet(db),
            int(time.mktime(start.timetuple())),
        )
        db.execute(sql, sql_args)

        # Clock in
        args.extend(
            ['--at', str(start)]
        )
        in_(db, args)
    except IndexError as e:
        print (
            "Backdate requires at least one argument: START. "
            "Please use either the format \"YYY-MM-DD HH:MM\" or "
            "a time offset like '1h 20m'."
        )
        logger.exception(e)



@command('alter the description of the active period', aliases=('write',))
def alter(db, args):
    parser = optparse.OptionParser(usage='''usage: %prog alter NOTES...

Inserts a note associated with the currently active period in the \
timesheet. For example, ``t alter Documenting timebook.``''')
    parser.add_option('-t', '--ticket', dest='ticket_number', type='string',
            default=None, help='Set ticket number'
            )
    parser.add_option('--billable', dest='billable', action='store_true',
            default=None, help='Marks entry as billable'
            )
    parser.add_option('--non-billable', dest='billable', action='store_false',
            default=None, help='Marks entry as billable'
            )
    parser.add_option('--id', dest='entry_id', type='string',
            default=None, help='Entry ID number (defaults to current)'
            )
    cmdutil.add_user_specified_attributes(db, parser)
    opts, args = parser.parse_args(args=args)

    if not opts.entry_id:
        active = dbutil.get_current_active_info(db)
        if active is None:
            raise SystemExit('error: timesheet not active')
        entry_id = active[0]
    else:
        entry_id = opts.entry_id
    if args:
        db.execute(u'''
        update
            entry
        set
            description = ?
        where
            entry.id = ?
        ''', (' '.join(args), entry_id))
    meta = cmdutil.collect_user_specified_attributes(db, opts)
    if opts.billable != None:
        meta['billable'] = 'yes' if opts.billable else 'no'
    if opts.ticket_number != None:
        meta['ticket_number'] = opts.ticket_number
    dbutil.update_entry_meta(db, entry_id, meta)


@command('show all running timesheets', aliases=('active',), read_only=True)
def running(db, args):
    parser = optparse.OptionParser(usage='''usage: %prog running

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
         aliases=('info',), read_only=True)
def now(db, args):
    parser = optparse.OptionParser(usage='''usage: %prog now [TIMESHEET]

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
        raise SystemExit('%(prog)s: error: sheet is empty. For program \
usage, see "%(prog)s --help".' % {'prog': os.path.basename(sys.argv[0])})
    running = dbutil.get_active_info(db, sheet)
    notes = ''
    if running is None:
        active = 'not active'
    else:
        duration = str(timedelta(seconds=running[0]))
        meta = dbutil.get_entry_meta(db, running[2])
        meta_string = ', '.join(['%s: %s' % (k, v) for k, v in meta.items()])
        description = running[1]

        details_parts = []
        if description:
            details_parts.append(description)
        if meta_string:
            details_parts.append(meta_string)

        active = '%s' % duration

        if details_parts:
            active = '%s (%s)' % (
                active,
                '; '.join(details_parts)
            )

    if opts.notes:
        print notes
    else:
        print '%s: %s' % (sheet, active)


@command('insert a new timesheet entry at a specified time')
def insert(db, args):
    try:
        start = datetime.strptime(args[0], "%Y-%m-%d %H:%M")
        end = datetime.strptime(args[1], "%Y-%m-%d %H:%M")
        memo = args[2]

        sql = """INSERT INTO entry (sheet, start_time, end_time, description)
            VALUES (?, ?, ?, ?)"""
        args = (
                    dbutil.get_current_sheet(db),
                    int(time.mktime(start.timetuple())),
                    int(time.mktime(end.timetuple())),
                    memo
                )
        db.execute(sql, args)
    except (ValueError, IndexError, ) as e:
        print "Insert requires three arguments, START END DESCRIPTION. \
Please use the date format \"YYYY-MM-DD HH:MM\""
        logger.exception(e)


@command('change details about a specific entry in the timesheet')
def modify(db, args):
    if len(args) < 1:
        raise exceptions.CommandError("You must select the ID number of an entry \
of you'd like to modify.")
    id = args[0]
    db.execute(u"""
        SELECT start_time, end_time, description
        FROM entry WHERE id = ?
    """, (id, ))
    row = db.fetchone()
    if not row:
        raise exceptions.CommandError("The ID you specified does not exist.")
    start = datetime.fromtimestamp(row[0])
    try:
        end = datetime.fromtimestamp(row[1])
    except TypeError:
        end = None

    new_start_date = rawinput_date_format(
                "Start Date",
                "%Y-%m-%d",
                start,
            )
    new_start_time = rawinput_date_format(
                "Start Time",
                "%H:%M",
                start
            )
    start = datetime(
                new_start_date.year,
                new_start_date.month,
                new_start_date.day,
                new_start_time.hour,
                new_start_time.minute,
            )
    new_end_date = rawinput_date_format(
                "End Date",
                "%Y-%m-%d",
                end,
            )
    if new_end_date:
        new_end_time = rawinput_date_format(
                    "End Time",
                    "%H:%M",
                    end,
                )
        if new_end_date and new_end_time:
            end = datetime(
                        new_end_date.year,
                        new_end_date.month,
                        new_end_date.day,
                        new_end_time.hour,
                        new_end_time.minute,
                    )
    description = raw_input("Description (\"%s\"):\t" % (
            row[2]
        ))
    if not description:
        description = row[2]

    sql = """
        UPDATE entry
        SET start_time = ?, end_time = ?, description = ? WHERE id = ?
        """
    args = (
            int(time.mktime(start.timetuple())),
            int(time.mktime(end.timetuple())) if end else None,
            description,
            id
        )
    db.execute(sql, args)


@command('get ticket details', read_only=True)
def details(db, args):
    ticket_number = args[0]
    try:
        db.execute("""
            SELECT project, details FROM ticket_details WHERE number = ?
            """, (ticket_number, ))
        details = db.fetchall()[0]

        print "Project: %s" % details[0]
        print "Title: %s" % details[1]

        db.execute("""
            SELECT
                SUM(
                    ROUND(
                        (
                            COALESCE(end_time, strftime('%s', 'now'))
                            - start_time
                        )
                        / CAST(3600 AS FLOAT)
                    , 2)
                ) AS hours
            FROM ticket_details
            INNER JOIN entry_details ON
                entry_details.ticket_number = ticket_details.number
            INNER JOIN entry ON
                entry_details.entry_id = entry.id
            WHERE ticket_number = ?
            """, (ticket_number, ))
        total_hours = db.fetchall()[0][0]

        db.execute("""
            SELECT
                SUM(
                    ROUND(
                        (
                            COALESCE(end_time, strftime('%s', 'now'))
                            - start_time
                        )
                        / CAST(3600 AS FLOAT)
                    , 2)
                ) AS hours
            FROM ticket_details
            INNER JOIN entry_details ON
                entry_details.ticket_number = ticket_details.number
            INNER JOIN entry ON
                entry_details.entry_id = entry.id
            WHERE billable = 1 AND ticket_number = ?
            """, (ticket_number, ))
        total_billable = db.fetchall()[0][0]
        if not total_billable:
            total_billable = 0

        print "Total Hours: %s (%s%% billable)" % (
                    total_hours,
                    round(total_billable / total_hours * 100, 2)
                )
    except IndexError as e:
        print "No information available."


@command('get timesheet statistics', locking=False, read_only=True)
def stats(db, args):
    parser = optparse.OptionParser(usage='''usage: %prog stats''')
    parser.add_option('-s', '--start', dest='start', type='string',
                      metavar='DATE',
                      default=(
                          datetime.now() - timedelta(days=7)
                        ).strftime('%Y-%m-%d'),
                      help='Show only entries \
starting after 00:00 on this date. The date should be of the format \
YYYY-MM-DD.')
    parser.add_option('-e', '--end', dest='end', type='string',
                      metavar='DATE',
                      default=datetime.now().strftime('%Y-%m-%d'),
                      help='Show only entries \
ending before 00:00 on this date. The date should be of the format \
YYYY-MM-DD.')
    opts, args = parser.parse_args(args=args)

    start_date = datetime.strptime(opts.start, "%Y-%m-%d")
    end_date = datetime.strptime(opts.end, "%Y-%m-%d")

    print "Statistics for %s through %s" % (
                opts.start, opts.end
            )

    db.execute("""
        SELECT
            COALESCE(billable, 0),
            SUM(
                ROUND(
                    (
                        COALESCE(end_time, strftime('%s', 'now'))
                        - start_time
                    )
                    / CAST(3600 AS FLOAT)
                , 2)
            ) as hours
        FROM entry
        LEFT JOIN entry_details ON entry_details.entry_id = entry.id
        WHERE
            start_time > STRFTIME('%s', ?, 'utc')
            and (
                end_time < STRFTIME('%s', ?, 'utc', '1 day')
                or end_time is null
            )
        AND sheet = 'default'
        GROUP BY billable
        ORDER BY billable
        """, (start_date, end_date))
    results = db.fetchall()

    billable_hours = 0
    total_hours = 0
    for result in results:
        if result[0] == 1:
            billable_hours = billable_hours + result[1]
        total_hours = total_hours + result[1]

    print "Total Hours: %s (%s%% billable)" % (
                round(total_hours, 2),
                round(billable_hours / total_hours * 100, 2)
            )

    db.execute("""
        SELECT
            project,
            SUM(
                ROUND(
                    (COALESCE(end_time, strftime('%s', 'now')) - start_time)
                    / CAST(3600 AS FLOAT), 2)
            ) as hours
        FROM entry_details
        INNER JOIN entry ON entry_details.entry_id = entry.id
        LEFT JOIN ticket_details ON
            ticket_details.number = entry_details.ticket_number
        WHERE start_time > STRFTIME('%s', ?, 'utc')
            and (
                end_time < STRFTIME('%s', ?, 'utc', '1 day')
                OR end_time is null
            )
        AND sheet = 'default'
        GROUP BY project
        ORDER BY hours DESC
        """,
            (start_date, end_date)
            )
    rows = db.fetchall()

    print "\nProject time allocations"
    for row in rows:
        print "%s%%\t%s\t%s" % (
                    round((row[1] / total_hours) * 100, 2),
                    row[1],
                    row[0]
                )

    db.execute("""
        SELECT
            details,
            number,
            SUM(
                ROUND(
                    (COALESCE(end_time, strftime('%s', 'now')) - start_time)
                    / CAST(3600 AS FLOAT), 2)
            ) as hours
        FROM entry_details
        INNER JOIN entry ON entry_details.entry_id = entry.id
        INNER JOIN ticket_details ON
            ticket_details.number = entry_details.ticket_number
        WHERE start_time > STRFTIME('%s', ?, 'utc')
            and (
                end_time < STRFTIME('%s', ?, 'utc', '1 day')
                OR end_time is null
            )
        AND sheet = 'default'
        GROUP BY details, number
        ORDER BY hours DESC
        LIMIT 10
        """,
            (start_date, end_date)
            )
    rows = db.fetchall()

    print "\nBiggest Tickets"
    for row in rows:
        print "%s%%\t%s\t%s\t%s" % (
                    round((row[2] / total_hours) * 100, 2),
                    row[2],
                    row[1],
                    row[0]
                )


@command('display timesheet, by default the current one',
         aliases=('export', 'format', 'show'), read_only=True)
def display(db, args):
    # arguments
    parser = optparse.OptionParser(usage='''usage: %prog display [TIMESHEET]

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
    parser.add_option('-i', '--show-ids', dest='show_ids',
            action='store_true', default=False)
    opts, args = parser.parse_args(args=args)

    # grab correct sheet
    if args:
        sheet = cmdutil.complete(dbutil.get_sheet_names(db), args[0],
                                 'timesheet')
    else:
        sheet = dbutil.get_current_sheet(db)

    #calculate "where"
    where = ''
    if opts.start is not None:
        start = cmdutil.parse_date_time(opts.start)
        where += ' and start_time >= %s' % start
    else:
        where += ''' and start_time >
            STRFTIME(\'%s\', \'now\', \'-7 days\', \'start of day\', \'utc\')
        '''
    if opts.end is not None:
        end = cmdutil.parse_date_time(opts.end)
        where += ' and end_time <= %s' % end
    if opts.format == 'plain':
        format_timebook(db, sheet, where, show_ids=opts.show_ids)
    elif opts.format == 'csv':
        format_csv(db, sheet, where, show_ids=opts.show_ids)
    else:
        raise SystemExit('Invalid format: %s' % opts.format)


def format_csv(db, sheet, where, show_ids=False):
    import csv

    writer = csv.writer(sys.stdout)
    writer.writerow(('Start', 'End', 'Length', 'Description'))
    db.execute(u'''
    select
       start_time,
       end_time,
       ifnull(end_time, strftime('%%s', 'now')) -
           start_time,
       description,
       id
    from
       entry
    where
       sheet = ? and
       end_time is not null%s
    ''' % where, (sheet,))
    format = lambda t: datetime.fromtimestamp(t).strftime(
        '%m/%d/%Y %H:%M:%S')
    rows = db.fetchall()
    if(show_ids):
        writer.writerows(
            map(
                lambda row: (
                    format(row[0]),
                    format(row[1]),
                    row[2],
                    row[3],
                    row[4]
                ),
                rows
            )
        )
    else:
        writer.writerows(
            map(
                lambda row: (
                    format(row[0]),
                    format(row[1]),
                    row[2],
                    row[3]
                ),
                rows
            )
        )
    total_formula = '=SUM(C2:C%d)/3600' % (len(rows) + 1)
    writer.writerow(('Total', '', total_formula, ''))


def format_timebook(db, sheet, where, show_ids=False):
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
    day_total = None
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
        ifnull(e.description, '') as description,
        id
    from
        entry e
    where
        e.sheet = ?%s
    order by
        day asc;
    ''' % where, (sheet,))
    entries = db.fetchall()

    # Get list of total metadata keys
    db.execute(u'''
    select
        distinct key, count(entry_id)
    from entry_meta
    inner join entry
        on entry.id = entry_meta.entry_id
    where
        entry.sheet = ?
        %s
    group by key
    order by count(entry_id) desc
    ''' % where, (sheet, ))
    metadata_keys = db.fetchall()
    extra_count = len(metadata_keys)
    if show_ids:
        extra_count = extra_count + 1 

    table = []
    table_header = ['Day', 'Start      End', 'Duration']
    for key in metadata_keys:
        table_header.append(
                    key[0].title().replace('_', ' ')
                )
    table_header.append('Notes')
    if show_ids:
        table_header.append('ID')
    table.append(table_header)
    for i, (day, start, end, duration, description, id) in \
            enumerate(entries):
        id = str(id)
        date = displ_date(start)
        diff = displ_total(duration)
        if end is None:
            trange = '%s -' % displ_time(start)
        else:
            trange = '%s - %s' % (displ_time(start), displ_time(end))
        if last_day == day:
            # If this row doesn't represent the first entry of the
            # day, don't display anything in the day column.
            row = ['']
        else:
            if day_total:
                table.append(['', '', displ_total(day_total), '']
                    + [''] * extra_count
                )
            row = [date]
            cur_day, day_total = days_iter.next()
        row.extend([
                trange, diff
            ])
        ticket_metadata = dbutil.get_entry_meta(db, id)
        for meta in metadata_keys:
            key = meta[0]
            row.append(
                        ticket_metadata[key] if (
                                key in ticket_metadata.keys()
                            ) else ''
                    )
        row.append(description)
        if show_ids:
            row.append(id)
        table.append(row)
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
    table += [['', '', displ_total(day_total), ''] + [''] * extra_count,
              ['Total', '', total, '',] + [''] * extra_count]
    cmdutil.pprint_table(table, footer_row=True)
