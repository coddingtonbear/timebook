# __init__.py
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
__version__ = (2, 0, 3)

def get_version():
    return '.'.join(str(bit) for bit in __version__)

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

if sys.platform == 'darwin':
    HOME_DIR = "/Users"
elif sys.platform == 'linux2':
    HOME_DIR = "/home"

logger = logging.getLogger('timebook')
logger.setLevel(logging.DEBUG)

handler = logging.StreamHandler(sys.stderr)
handler.setLevel(logging.INFO)
logger.addHandler(handler)

CONFIG_DIR = os.path.expanduser(os.path.join(
        get_user_path(
            get_best_user_guess()
            )
    , ".config", "timebook"))
CONFIG_FILE = os.path.join(CONFIG_DIR, "timebook.ini")
TIMESHEET_DB = os.path.join(CONFIG_DIR, "sheets.db")
