# db.py
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

import sqlite3

from timebook.migrations import MigrationManager


class Database(object):
    def __init__(self, path, config):
        self.config = config
        self.path = path
        self.connection = sqlite3.connect(path, isolation_level=None)
        self.cursor = self.connection.cursor()
        for attr in ('execute', 'executescript', 'fetchone', 'fetchall'):
            setattr(self, attr, getattr(self.cursor, attr))
        self._initialize_db()

    @property
    def db_version(self):
        try:
            self.execute('''
                SELECT value FROM meta WHERE key = 'db_version'
            ''')
            return int(self.fetchone()[0])
        except:
            return 0

    def _initialize_db(self):
        manager = MigrationManager(self)
        manager.upgrade()
