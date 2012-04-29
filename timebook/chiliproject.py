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

class ChiliprojectConnector(object):
    def __init__(self, db, username=None, password=None):
        from timebook.db import Database
        self.db = db
        self.loaded = False

        self.domain = self.db.config.get_with_default(
                'chiliproject', 
                'domain', 
                'chili.parthenonsoftware.com'
                )
        self.issue_format = 'http://%s/issues/%%s.json' % self.domain
        if not username or not password:
            try:
                self.username = self.db.config.get("auth", "username")
                self.password = self.db.config.get("auth", "password")
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
                request = urllib2.Request(self.issue_format % ticket_number)
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
