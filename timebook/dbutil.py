# dbutil.py
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

import datetime
import re
import time

from timebook.chiliproject import ChiliprojectConnector


def get_current_sheet(db):
    db.execute(u'''
    select
        value
    from
        meta
    where
        key = 'current_sheet'
    ''')
    return db.fetchone()[0]


def get_sheet_names(db):
    db.execute(u'''
    select
        distinct sheet
    from
        entry
    ''')
    return tuple(r[0] for r in db.fetchall())


def get_active_info(db, sheet):
    db.execute(u'''
    select
        strftime('%s', 'now') - entry.start_time,
        entry.description,
        id
    from
        entry
    where
        entry.sheet = ? and
        entry.end_time is null
    ''', (sheet,))
    return db.fetchone()


def get_current_active_info(db):
    db.execute(u'''
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
    return db.fetchone()


def get_current_start_time(db):
    db.execute(u'''
    select
        entry.id,
        entry.start_time
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
    return db.fetchone()


def get_entry_count(db, sheet):
    db.execute(u'''
    select
        count(*)
    from
        entry e
    where
        sheet = ?
    ''', (sheet,))
    return db.fetchone()[0]


def get_most_recent_clockout(db, sheet):
    db.execute(u'''
    select
        id, start_time, end_time, description
    from
        entry
    where
        sheet = ?
    order by
        -end_time
    ''', (sheet,))
    return db.fetchone()


def update_entry_meta(db, id, meta):
    existing_meta = get_entry_meta(db, id)
    for key, value in meta.items():
        if key in existing_meta.keys() and value != existing_meta[key]:
            db.execute(u'''
            update
                entry_meta
            set 
                value = ?
            where 
                key = ?
                and
                entry_id = ?
            ''', (
                    value,
                    key,
                    id,
                )
            )
        else:
            db.execute(u'''
            insert into
                entry_meta
                (key, value, entry_id)
            values
                (?, ?, ?)
            ''', (
                    key,
                    value,
                    id
                )
            )


def get_entry_meta(db, id):
    meta = {}
    db.execute(u'''
    select
        key, value
    from 
        entry_meta
    where
        entry_id = ?
    order by
        key
    ''', (id, ))
    for row in db.fetchall():
        key = row[0]
        value = row[1]
        meta[key] = value
    return meta


def date_is_vacation(db, year, month, day):
    db.execute(u'''
    select
        count(*)
    from
        vacation
    where year = ?
    and month = ?
    and day = ?
    ''', (year, month, day,))
    if db.fetchone()[0] > 0:
        return True
    return False


def date_is_holiday(db, year, month, day):
    db.execute(u'''
    select
        count(*)
    from
        holidays
    where year = ?
    and month = ?
    and day = ?
    ''', (year, month, day,))
    if db.fetchone()[0] > 0:
        return True
    return False


def date_is_unpaid(db, year, month, day):
    db.execute(u'''
    select
        count(*)
    from
        unpaid
    where year = ?
    and month = ?
    and day = ?
    ''', (year, month, day,))
    if db.fetchone()[0] > 0:
        return True
    return False


def date_is_untracked(db, year, month, day):
    untracked_checks = [
            date_is_vacation,
            date_is_holiday,
            date_is_unpaid,
            ]
    for check in untracked_checks:
        if check(db, year, month, day):
            return True
    return False


class TimesheetRow(object):
    TICKET_MATCHER = re.compile(
            r"^(?:(\d{4,6})(?:[^0-9]|$)+|.*#(\d{4,6})(?:[^0-9]|$)+)"
        )
    TICKET_URL = "http://chili.parthenonsoftware.com/issues/%s/"

    def __init__(self):
        self.lookup_handler = False
        self.db = False
        self.meta = {}

    @staticmethod
    def from_row(row):
        t = TimesheetRow()
        t.id = row[0]
        t.start_time_epoch = row[1]
        t.end_time_epoch = row[2]
        t.description = row[3]
        t.hours = row[4]
        return t

    def set_meta(self, meta):
        self.meta = meta

    def meta_key_has_value(self, key):
        if key in self.meta.keys() and self.meta[key]:
            return True
        return False

    def set_lookup_handler(self, handler):
        self.lookup_handler = handler

    @property
    def is_active(self):
        if not self.end_time_epoch:
            return True
        return False

    @property
    def chili_detail(self):
        if self.lookup_handler:
            if self.ticket_number:
                return self.lookup_handler.get_description_for_ticket(
                        self.ticket_number
                    )

    @property
    def start_time(self):
        return datetime.datetime.fromtimestamp(float(self.start_time_epoch))

    @property
    def end_time(self):
        if self.end_time_epoch:
            return datetime.datetime.fromtimestamp(float(self.end_time_epoch))

    @property
    def is_ticket(self):
        if self.meta_key_has_value('ticket_number'):
            return True
        elif self.description and self.ticket_number:
            return True
        return False

    @property
    def ticket_number(self):
        if self.meta_key_has_value('ticket_number'):
            return self.meta['ticket_number']
        elif self.description:
            matches = self.TICKET_MATCHER.match(self.description)
            if matches:
                for match in matches.groups():
                    if match:
                        return match
        return None

    @property
    def timesheet_description(self):
        if self.description:
            return self.description
        else:
            return ''

    @property
    def is_billable(self):
        if self.meta_key_has_value('billable'):
            return True if self.meta['billable'] == 'yes' else False
        elif self.description:
            ticket_match = re.match(r"^(\d{4,6})$", self.description)
            force_billable_search = re.search(
                    r"\(Billable\)",
                    self.description,
                    re.IGNORECASE
                )
            if ticket_match:
                return True
            if force_billable_search:
                return True
        return False

    @property
    def ticket_url(self):
        return self.TICKET_URL % self.ticket_number

    @property
    def end_time_or_now(self):
        return datetime.datetime.fromtimestamp(
                float(self.end_time_epoch_or_now)
            )

    @property
    def end_time_epoch_or_now(self):
        if self.end_time_epoch:
            return self.end_time_epoch
        else:
            return time.time()

    @property
    def total_hours(self):
        return float(self.end_time_epoch_or_now - self.start_time_epoch) / 3600

    def __str__(self):
        return """%s - %s; %s""" % (
                    self.start_time,
                    self.end_time_or_now,
                    self.description if not self.ticket_number else "%s%s" % (
                            self.ticket_number,
                            " (" + self.chili_detail + ")"
                            if self.chili_detail else ""
                        ),
                )

CHILIPROJECT_LOOKUP = None


def timesheet_row_factory(cursor, row):
    global CHILIPROJECT_LOOKUP
    if not CHILIPROJECT_LOOKUP:
        CHILIPROJECT_LOOKUP = ChiliprojectConnector()
    ts = TimesheetRow.from_row(row)
    ts.set_lookup_handler(CHILIPROJECT_LOOKUP)
    return ts


def dict_factory(cursor, row):
    d = {}
    for idx, col in enumerate(cursor.description):
        d[col[0]] = row[idx]
    return d
