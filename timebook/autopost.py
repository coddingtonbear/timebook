import sqlite3
import os.path
import getpass
import datetime
import re
import ConfigParser
import urllib
import urllib2

LOGIN_URL = "http://www.parthenonsoftware.com/timesheet/index.php"
TIMESHEET_URL = "http://www.parthenonsoftware.com/timesheet/timesheet.php"
TIMESHEET_DB = "~/.config/timebook/sheets.db"
CONFIG = "~/.timetracker"

class TimesheetEntry(object):
    def __init__(self, start, end, description):
        self.start = datetime.datetime.fromtimestamp(float(start))
        self.end = datetime.datetime.fromtimestamp(float(end))

        (self.description, self.ticket_number, self.billable, ) = self.parse_description(description)

    def parse_description(self, description):
        ticket_number = None
        entry_text = None
        billable = None

        if(description):
            ticket_match = re.match(r"^(\d{4})$", description)
            ticket_search = re.search(r"(\d{4})", description)
            force_billable_search = re.search(r"\(Billable\)", description, re.IGNORECASE)
            if(ticket_match):
                ticket_number = ticket_match.groups()[0]
                entry_text = ""
                billable = True
            elif(force_billable_search):
                ticket_number = None
                entry_text = description
                billable = True
            elif(ticket_search):
                ticket_number = ticket_search.groups()[0]
                entry_text = description
                billable = False
            else:
                ticket_number = None
                entry_text = description
                billable = False
        else:
            ticket_number = None
            entry_text = ""
            billable = False
        return (entry_text, ticket_number, billable, )

    def __str__(self):
        ticket_number = ""
        billable = "(Not Billable)"
        if(self.ticket_number):
            ticket_number = "%s " % self.ticket_number
        if(self.billable):
            billable = ""
        return "%s - %s; %s%s %s" % (
                self.start, self.end,
                ticket_number,
                self.description,
                billable
                )

class ParthenonTimeTracker(object):
    def __init__(self, login_url, timesheet_url, timesheet_db, config, date):
        self.timesheet_url = timesheet_url
        self.timesheet_db = timesheet_db
        self.login_url = login_url
        self.config = self.load_configuration(config)
        self.date = date

    def load_configuration(self, configfile):
        configfile = os.path.expanduser(configfile)
        co = ConfigParser.SafeConfigParser()
        if(os.path.exists(configfile)):
            co.read(configfile)
        return co

    def get_config(self, section, option):
        if(not self.config):
            raise Exception("!!!")
        try:
            return self.config.get(section, option)
        except (ConfigParser.NoSectionError, ConfigParser.NoOptionError), e:
            if(option.upper().find("pass") or option[0:1] == "_"):
                return getpass.getpass("%s: " % option.capitalize())
            else:
                return raw_input("%s: " % option.capitalize())    

    def main(self):
        print "Posting hours for %s" % self.date
        entries = self.get_entries(self.date)
        for entry in entries:
            print entry
        
        username = self.get_config('auth', 'username')
        password = self.get_config('auth', 'password')
        opener = self.login(self.login_url, username, password)
        result = self.post_entries(opener, self.timesheet_url, self.date, entries)

    def post_entries(self, opener, url, date, entries):
        data = [
                ('__tcAction[saveTimesheet]', 'save'),
                ('date', date.strftime('%Y-%m-%d')),
                ]
        for entry in entries:
            data.append(('starthour[]', entry.start.strftime('%H')))
            data.append(('startmin[]', entry.start.strftime('%M')))
            data.append(('endhour[]', entry.end.strftime('%H')))
            data.append(('endmin[]', entry.end.strftime('%M')))
            if(entry.ticket_number):
                data.append(('mantisid[]', entry.ticket_number))
            else:
                data.append(('mantisid[]', ''))
            data.append(('description[]', entry.description))
            if(entry.billable):
                data.append(('debug[]', '0'))
            else:
                data.append(('debug[]', '1'))

        data_encoded = urllib.urlencode(data)
        r = opener.open("%s?date=%s" % (url, date.strftime("%Y-%m-%d")), data_encoded)

    def get_db(self):
        db = sqlite3.connect(
            os.path.expanduser(
                self.timesheet_db
                )
            )
        return db

    def get_entries(self, day):
        db = self.get_db()
        cursor = db.cursor()
        cursor.execute("""
            SELECT
                start_time,
                COALESCE(end_time, STRFTIME('%s', 'now')),
                description
            FROM
                entry
            WHERE
                start_time > STRFTIME('%s', ?, 'utc')
                AND
                start_time < STRFTIME('%s', ?, 'utc', '1 day')
            """, (day.strftime("%Y-%m-%d"), day.strftime("%Y-%m-%d"), ))
        results = cursor.fetchall()

        final_results = []
        for result in results:
            entry = TimesheetEntry(result[0], result[1], result[2])
            final_results.append(entry)
        return final_results

    def login(self, login_url, username, password):
        opener = urllib2.build_opener(urllib2.HTTPCookieProcessor())
        urllib2.install_opener(opener)
        data = urllib.urlencode((
                ('username', username),
                ('password', password),
            ))
        opener.open(login_url, data)
        return opener

    def __enter__(self, *args, **kwargs):
        return self

    def __exit__(self, *args, **kwargs):
        return True

