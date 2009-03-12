# db.py
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

import sqlite3

class Database(object):
    def __init__(self, path, config):
        self.config = config
        self.path = path
        connection = sqlite3.connect(path, isolation_level=None)
        cursor = connection.cursor()
        for attr in ('execute', 'executescript', 'fetchone', 'fetchall'):
            setattr(self, attr, getattr(cursor, attr))
        self._initialize_db()

    def _initialize_db(self):
        self.executescript(u'''
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
