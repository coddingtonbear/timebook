# __init__.py
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

from ConfigParser import ConfigParser
import base64
import datetime
import json
import logging
import os.path
import re
import time
import urllib2

__author__ = 'Trevor Caira <trevor@caira.com>, Adam Coddington <me@adamcoddington.net>'
__version__ = (1, 5, 0)

def get_version():
    return '.'.join(str(bit) for bit in __version__)

HOME_DIR = "/home/"
def get_user_path(guess):
    """
    Using a supplied username, get the homedir path.
    """
    return os.path.join(HOME_DIR, guess)

def get_best_user_guess():
    """
    Searches for the most recently modified timebook database to find the
    most reasonable user.
    """
    dirs = os.listdir(HOME_DIR)
    max_atime = 0;
    final_user = None;
    for homedir in dirs:
        timebook_db_file = os.path.join(
                        HOME_DIR,
                        homedir,
                        ".config/timebook/sheets.db"
                    )
        if os.path.exists(timebook_db_file):
            if os.stat(timebook_db_file).st_atime > max_atime:
                final_user = homedir
    return final_user

logger = logging.getLogger('timebook')
logger.setLevel(logging.DEBUG)

LOGIN_URL = "http://www.parthenonsoftware.com/timesheet/index.php"
TIMESHEET_URL = "http://www.parthenonsoftware.com/timesheet/timesheet.php"
CONFIG_DIR = os.path.expanduser(os.path.join(
        get_user_path(
            get_best_user_guess()
            )
    , ".config", "timebook"))
CONFIG_FILE = os.path.join(CONFIG_DIR, "timebook.ini")
TIMESHEET_DB = os.path.join(CONFIG_DIR, "sheets.db")
CONFIG_OLD = os.path.join(get_user_path(get_best_user_guess()), ".timetracker")
CHILIPROJECT_ISSUE = "http://chili.parthenonsoftware.com/issues/%s.json"
LOGS = os.path.join(
                os.path.dirname(__file__),
                "logs/",
                "web.log"
            )

class ChiliprojectLookupHelper(object):
    PROJECT_CACHE = {}

    def __init__(self):
        from timebook.db import Database
        self.config = ConfigParser()
        self.loaded = False
        self.config.read([CONFIG_OLD, CONFIG_FILE ])
        try:
            self.db = Database(
                    TIMESHEET_DB,
                    CONFIG_FILE
                )
            self.username = self.config.get("auth", "username")
            self.password = self.config.get("auth", "password")
            self.loaded = True
        except Exception as e:
            logger.exception(e)

    def get_ticket_info_from_db(self, ticket_number):
        return self.db.execute("""
            SELECT project, details FROM ticket_info
            """)[0]

    def get_description_for_ticket(self, ticket_number):
        if not self.loaded:
            return None
        else:
            try:
                logger.info(self.get_ticket_info_from_db(ticket_number))
                if ticket_number in self.PROJECT_CACHE.keys():
                    data = self.PROJECT_CACHE[ticket_number]
                else:
                    request = urllib2.Request(CHILIPROJECT_ISSUE % ticket_number)
                    request.add_header(
                                "Authorization",
                                base64.encodestring(
                                        "%s:%s" % (
                                                self.username,
                                                self.password
                                            )
                                    ).replace("\n", "")
                            )
                    result = urllib2.urlopen(request).read()
                    data = json.loads(result)
                    self.PROJECT_CACHE[ticket_number] = data
                return "%s: %s" % (
                            data["issue"]["project"]["name"],
                            data["issue"]["subject"],
                        )
            except Exception as e:
                logger.exception(e)

class TimesheetRow(object):
    TICKET_MATCHER = re.compile(r"^(\d{4,6})(?:[^0-9]|$)+")
    TICKET_URL = "http://chili.parthenonsoftware.com/issues/%s/"

    def __init__(self):
        self.lookup_handler = False

    @staticmethod
    def from_row(row):
        t = TimesheetRow()
        t.id = row[0]
        t.start_time_epoch = row[1]
        t.end_time_epoch = row[2]
        t.description = row[3]
        t.hours = row[4]
        return t

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
                return self.lookup_handler.get_description_for_ticket(self.ticket_number)

    @property
    def start_time(self):
        return datetime.datetime.fromtimestamp(float(self.start_time_epoch))

    @property
    def end_time(self):
        if self.end_time_epoch:
            return datetime.datetime.fromtimestamp(float(self.end_time_epoch))

    @property
    def is_ticket(self):
        if self.description and self.TICKET_MATCHER.match(self.description):
            return True

    @property
    def ticket_number(self):
        if self.is_ticket:
            return self.TICKET_MATCHER.match(self.description).groups()[0]

    @property
    def ticket_url(self):
        if self.is_ticket:
            return self.TICKET_URL % self.TICKET_MATCHER.match(self.description).groups()[0]

    @property
    def end_time_epoch_or_now(self):
        if self.end_time_epoch:
            return self.end_time_epoch
        else:
            return time.time()

    @property
    def total_hours(self):
        return float(self.end_time_epoch_or_now - self.start_time_epoch) / 3600

CHILIPROJECT_LOOKUP = None
def timesheet_row_factory(cursor, row):
    global CHILIPROJECT_LOOKUP
    if not CHILIPROJECT_LOOKUP:
        CHILIPROJECT_LOOKUP = ChiliprojectLookupHelper()
    ts = TimesheetRow.from_row(row)
    ts.set_lookup_handler(CHILIPROJECT_LOOKUP)
    return ts

def dict_factory(cursor, row):
    d = {}
    for idx,col in enumerate(cursor.description):
        d[col[0]] = row[idx]
    return d

