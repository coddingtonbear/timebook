from timebook.migrations import Migration


class HourAdjustmentsMigration(Migration):
    def run(self):
        self.db.executescript(u'''
        CREATE TABLE if not exists adjustments (
            timestamp integer not null,
            adjustment float,
            description text
        );
        ''')
