# dbutil.py
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
        entry.description
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
        end_time
    from
        entry
    where
        sheet = ?
    order by
        -end_time
    ''', (sheet,))
    row = db.fetchone()
    if not row:
        # we've never clocked out on this timesheet
        return None
    else:
        return row[0]
