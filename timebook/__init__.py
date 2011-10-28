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
import getpass
import json
import logging
import os.path
import re
import sqlite3
import sys
import time
import urllib2

__author__ = 'Trevor Caira <trevor@caira.com>, Adam Coddington <me@adamcoddington.net>'
__version__ = (1, 6, 0)

def get_version():
    return '.'.join(str(bit) for bit in __version__)

if sys.platform == 'darwin':
    HOME_DIR = "/Users"
elif sys.platform == 'linux2':
    HOME_DIR = "/home"

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
    if not final_user:
        final_user = getpass.getuser()
    return final_user

logger = logging.getLogger('timebook')
logger.setLevel(logging.DEBUG)

handler = logging.StreamHandler(sys.stderr)
handler.setLevel(logging.INFO)
logger.addHandler(handler)

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
    def __init__(self, username = None, password = None, db = None):
        from timebook.db import Database
        self.config = ConfigParser()
        self.loaded = False
        self.db = db
        if not self.db:
            self.db = Database(
                    TIMESHEET_DB,
                    CONFIG_FILE
                )
        if not username or not password:
            self.config.read([CONFIG_OLD, CONFIG_FILE ])
            try:
                self.username = self.config.get("auth", "username")
                self.password = self.config.get("auth", "password")
                self.loaded = True
            except Exception as e:
                logger.exception(e)
        else:
            self.loaded = True
            self.username = username
            self.password = password

    def store_ticket_info_in_db(self, ticket_number, project, details):
        logger.debug("Storing ticket information for %s" % ticket_number)
        try:
            self.db.execute("""
                INSERT INTO ticket_details (number, project, details)
                VALUES (?, ?, ?)
                """, (ticket_number, project, details, ))
        except sqlite3.OperationalError as e:
            logger.exception(e)

    def get_ticket_info_from_db(self, ticket_number):
        try:
            logger.debug("Checking in DB for %s" % ticket_number)
            return self.db.execute("""
                SELECT project, details FROM ticket_details
                WHERE number = ?
                """, (ticket_number, )).fetchall()[0]
        except IndexError as e:
            logger.debug("No information in DB for %s" % ticket_number)
            return None

    def get_ticket_details(self, ticket_number):
        data = self.get_ticket_info_from_db(ticket_number)

        if data:
            return data
        if not data:
            logger.debug("Gathering data from Chiliproject API")
            try:
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
                self.store_ticket_info_in_db(
                            ticket_number,
                            data["issue"]["project"]["name"],
                            data["issue"]["subject"],
                        )
                return (
                            data["issue"]["project"]["name"],
                            data["issue"]["subject"],
                        )
            except urllib2.HTTPError as e:
                logger.debug("Encountered an HTTP Exception while gathering data. %s" % e)
            except Exception as e:
                logger.exception(e)

    def get_description_for_ticket(self, ticket_number):
        data = self.get_ticket_details(ticket_number)
        if data:
            return "%s: %s" % (
                        data[0],
                        data[1]
                    )
        return None

class TimesheetRow(object):
    TICKET_MATCHER = re.compile(r"^(?:(\d{4,6})(?:[^0-9]|$)+|.*#(\d{4,6})(?:[^0-9]|$)+)")
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
        if self.description and self.ticket_number:
            return True

    @property
    def ticket_number(self):
        matches = self.TICKET_MATCHER.match(self.description)
        if not matches:
            return None
        else:
            for match in matches.groups():
                if match:
                    return match

    @property
    def timesheet_description(self):
        if self.ticket_number == self.description:
            return ''
        else:
            return self.description

    @property
    def is_billable(self):
        if self.description:
            ticket_match = re.match(r"^(\d{4,6})$", self.description)
            force_billable_search = re.search(r"\(Billable\)", self.description, re.IGNORECASE)
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
        return datetime.datetime.fromtimestamp(float(self.end_time_epoch_or_now))

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
                            " (" + self.chili_detail + ")" if self.chili_detail else ""
                        ),
                )

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

