# Copyright (c) 2011-2012 Adam Coddington
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
import getpass
import ConfigParser
import urllib
import urllib2

from timebook.chiliproject import ChiliprojectConnector
from timebook.dbutil import TimesheetRow, get_entry_meta


class TimesheetPoster(object):
    _config_section = 'timesheet_poster'

    def __init__(self, db, date):
        self.timesheet_url = db.config.get_with_default(
                self._config_section,
                'timesheet_url',
                'http://www.parthenonsoftware.com/timesheet/timesheet.php'
                )
        self.login_url = db.config.get_with_default(
                self._config_section,
                'login_url',
                'http://www.parthenonsoftware.com/timesheet/index.php'
                )
        self.date = date
        self.db = db

    def get_config(self, section, option):
        try:
            return self.db.config.get(section, option)
        except (ConfigParser.NoSectionError, ConfigParser.NoOptionError) as e:
            if(option.upper().find("pass") or option[0:1] == "_"):
                return getpass.getpass("%s: " % option.capitalize())
            else:
                return raw_input("%s: " % option.capitalize())

    def main(self):
        print "Posting hours for %s" % self.date
        self.username = self.get_config('auth', 'username')
        self.password = self.get_config('auth', 'password')

        entries = self.get_entries(self.date)
        for entry in entries:
            print entry
        opener = self.login(self.login_url, self.username, self.password)
        result = self.post_entries(
                opener,
                self.timesheet_url,
                self.date,
                entries
                )
        return result

    def post_entries(self, opener, url, date, entries):
        data = [
                ('__tcAction[saveTimesheet]', 'save'),
                ('date', date.strftime('%Y-%m-%d')),
                ]
        for entry in entries:
            data.append(('starthour[]', entry.start_time.strftime('%H')))
            data.append(('startmin[]', entry.start_time.strftime('%M')))
            data.append(('endhour[]', entry.end_time_or_now.strftime('%H')))
            data.append(('endmin[]', entry.end_time_or_now.strftime('%M')))
            data.append(
                    (
                        'mantisid[]',
                        entry.ticket_number if entry.ticket_number else ''
                    )
                )
            data.append(('description[]', entry.timesheet_description))
            data.append(('debug[]', '1' if not entry.is_billable else '0'))

        data_encoded = urllib.urlencode(data)
        r = opener.open(
                "%s?date=%s" % (
                    url,
                    date.strftime("%Y-%m-%d")
                ), data_encoded
            )
        return r

    def get_entries(self, day):
        self.db.execute("""
            SELECT
                id,
                start_time,
                COALESCE(end_time, STRFTIME('%s', 'now')) as end_time,
                description,
                ROUND(
                        (
                            COALESCE(end_time, strftime('%s', 'now'))
                            - start_time
                        )
                        / CAST(3600 AS FLOAT), 2
                    ) AS hours
            FROM
                entry
            WHERE
                start_time > STRFTIME('%s', ?, 'utc')
                AND
                start_time < STRFTIME('%s', ?, 'utc', '1 day')
                AND
                sheet = 'default'
            """, (day.strftime("%Y-%m-%d"), day.strftime("%Y-%m-%d"), ))
        results = self.db.fetchall()

        helper = ChiliprojectConnector(
                    self.db,
                    username=self.username,
                    password=self.password
                )

        final_results = []
        for result in results:
            entry = TimesheetRow.from_row(result)
            entry.set_lookup_handler(helper)
            entry.set_meta(
                        get_entry_meta(self.db, result[0])
                    )
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
