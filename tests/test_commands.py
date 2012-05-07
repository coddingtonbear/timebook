import datetime
import StringIO
import sys
import time
import unittest

import mock
import timebook.db
import timebook.commands as cmds

class TestCommandFunctions(unittest.TestCase):
    def setUp(self):
        config_mock = mock.Mock() 
        config_mock.get.return_value = False
        self.default_sheet = 'default'
        self.db_mock = timebook.db.Database(
                    ':memory:',
                    config_mock
                )
        self.arbitrary_args = []

        cmds.pre_hook = mock.Mock()
        cmds.post_hook = mock.Mock()

        self.now = int(time.time())
        cmds.cmdutil.parse_date_time_or_now = mock.Mock(
                    return_value = self.now
                )

    def adjust_output_rows_for_time(self, rows):
        processed = []
        for row in rows:
            processed_row = []
            for column in row:
                column = column.format(
                        time = datetime.datetime.fromtimestamp(
                            self.now
                            ).strftime('%H:%M:%S'),
                        date = datetime.datetime.fromtimestamp(
                            self.now
                            ).strftime('%b %d, %Y'),
                    )
                processed_row.append(column)
            processed.append(processed_row)
        return processed

    def capture_output(self, cmd, args = None, kwargs = None):
        if not args:
            args = []
        if not kwargs:
            kwargs = {}
        real_out = sys.stdout
        sys.stdout = StringIO.StringIO()
        cmd.__call__(*args, **kwargs)
        output = sys.stdout.getvalue().strip()
        sys.stdout = real_out
        return output

    def get_entry_rows(self):
        self.db_mock.execute('''
            select * from entry;
            ''')
        return self.db_mock.fetchall()

    def tabularize_output(self, output):
        output_rows = []

        rows = output.split('\n')
        for row in rows:
            this_row = []
            cols = row.split('\t')
            for col in cols:
                this_row.append(
                            col.strip()
                        )
            output_rows.append(
                        this_row
                    )
        return output_rows

    def test_backend(self):
        arbitrary_path = '/path/to/db/'
        sqlite3_binary = 'sqlite3'
        self.db_mock.path = arbitrary_path

        cmds.subprocess.call = mock.MagicMock()
        cmds.backend(self.db_mock, self.arbitrary_args)

        cmds.subprocess.call.assert_called_with(
                    (
                        sqlite3_binary,
                        arbitrary_path,
                    )
                )

    def test_post(self):
        arbitrary_login_url = "http://some.url/"
        arbitrary_timesheet_url = "http://some.other.url/"
        arbitrary_db_path = "/path/to/some/db"
        arbitrary_config_file = "/path/to/some/file"

        cmds.LOGIN_URL = arbitrary_login_url
        cmds.TIMESHEET_URL = arbitrary_timesheet_url
        cmds.TIMESHEET_DB = arbitrary_db_path
        cmds.CONFIG_FILE = arbitrary_config_file

        cmds.TimesheetPoster= mock.MagicMock()

        cmds.post(self.db_mock, self.arbitrary_args)

        cmds.TimesheetPoster.assert_called_with(
                    self.db_mock,
                    datetime.datetime.fromtimestamp(self.now).date(),
                    fake = False
                )

        self.assertTrue(
                mock.call().__enter__().main() 
                in cmds.TimesheetPoster.mock_calls
            )

    def test_in(self):
        arbitrary_description = "Some Description"
        expected_row = (
                    1, 
                    self.default_sheet,
                    self.now,
                    None,
                    arbitrary_description,
                    None
                )
        args = [arbitrary_description]

        cmds.in_(self.db_mock, args)
        
        rows = self.get_entry_rows()

        self.assertEqual(
                    rows,
                    [expected_row, ]
                )

    def test_list_when_no_sheets(self):
        output = self.capture_output(
                    cmds.list,
                    [self.db_mock, self.arbitrary_args, ]
                )
        self.assertEqual(
                    output,
                    "(no sheets)"
                )

    def test_list_when_has_sheets(self):
        expected_rows = [
                [u'Timesheet   Running   Today     Total time'], 
                [u'*default     --        0:00:00   0:00:00']
            ]
        cmds.in_(self.db_mock, ['arbitrary description'])
        output = self.capture_output(
                    cmds.list,
                    [self.db_mock, self.arbitrary_args, ]
                )
        output = self.tabularize_output(output)
        self.assertEqual(
                output,
                expected_rows
            )

    def test_switch(self):
        args = [
                'Something New'
                ]
        cmds.switch(self.db_mock, args)

        current_sheet = cmds.dbutil.get_current_sheet(self.db_mock)

        self.assertEqual(
                    current_sheet,
                    args[0]
                )
    
    def test_out(self):
        expected_rows = [
                (
                    1, 
                    u'default', 
                    self.now, 
                    self.now, 
                    None, 
                    None
                )
            ]

        args = []
        cmds.in_(self.db_mock, args)
        cmds.out(self.db_mock, args)

        rows = self.get_entry_rows()

        self.assertEqual(
                rows,
                expected_rows
                )

    def test_out_single_sheet(self):
        expected_rows = [
                (
                    1, 
                    u'default', 
                    self.now, 
                    self.now, 
                    None, 
                    None
                ),
                (
                    2, 
                    u'another_sheet', 
                    self.now,
                    None, 
                    None, 
                    None
                )
            ]

        args = []
        cmds.in_(self.db_mock, args)
        cmds.switch(self.db_mock, ['another_sheet', ])
        cmds.in_(self.db_mock, args)
        cmds.switch(self.db_mock, ['default', ])
        cmds.out(self.db_mock, args)

        rows = self.get_entry_rows()

        self.assertEqual(
                rows,
                expected_rows
                )

    def test_out_all_sheets(self):
        expected_rows = [
                (
                    1, 
                    u'default', 
                    self.now, 
                    self.now, 
                    None, 
                    None
                ),
                (
                    2, 
                    u'another_sheet', 
                    self.now,
                    self.now,
                    None, 
                    None
                )
            ]

        args = []
        cmds.in_(self.db_mock, args)
        cmds.switch(self.db_mock, ['another_sheet', ])
        cmds.in_(self.db_mock, args)
        cmds.switch(self.db_mock, ['default', ])
        cmds.out(self.db_mock, ['--all'])

        rows = self.get_entry_rows()

        self.assertEqual(
                rows,
                expected_rows
                )

    def test_alter(self):
        original_name = 'current task'
        later_name = 'something else'
        expected_rows = [
                (
                    1, 
                    u'default', 
                    self.now, 
                    None,
                    later_name,
                    None
                ),
            ]
        cmds.in_(self.db_mock, [original_name, ])
        cmds.alter(self.db_mock, [later_name, ])

        rows = self.get_entry_rows()

        self.assertEqual(
                rows,
                expected_rows
            )

    def test_running(self):
        expected_rows = [
                [u'Timesheet   Description'], 
                [u'default     some task']
            ]
        cmds.in_(self.db_mock, ['some task', ])
        output = self.tabularize_output(
                self.capture_output(cmds.running, [
                        self.db_mock,
                        self.arbitrary_args,
                    ]
                )
            )
        self.assertEqual(
                    output,
                    expected_rows,
                )

    def test_display(self):
        expected_rows = self.adjust_output_rows_for_time([
                [u'Day            Start      End        Duration   Notes             Billable'], 
                [u'{date}'  + '   {time} - {time} ' +'  00:00:00   some task         yes'], 
                [u'{time} - '             + '           00:00:00   some other task   yes'], 
                [u'00:00:00'], 
                [u'Total                                00:00:00']
            ])
        cmds.in_(self.db_mock, ['some task', ])
        cmds.out(self.db_mock, [])
        cmds.in_(self.db_mock, ['some other task', ])

        output = self.tabularize_output(
                self.capture_output(
                        cmds.display,
                        [
                            self.db_mock,
                            self.arbitrary_args,
                        ]
                    )
                )

        self.assertEqual(
                    output,
                    expected_rows,
                )

if __name__ == '__main__':
    unittest.main()
