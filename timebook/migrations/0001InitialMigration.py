from timebook.migrations import Migration


class InitialMigration(Migration):
    def run(self):
        self.db.executescript(u'''
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
        create table if not exists entry_details (
            entry_id integer primary key not null,
            ticket_number integer default null,
            billable integer default 0
        );
        CREATE TABLE if not exists holidays (
            year integer default null,
            month integer,
            day integer
        );
        CREATE TABLE if not exists unpaid (
            year integer default null,
            month integer,
            day integer
        );
        CREATE TABLE if not exists vacation (
            year integer default null,
            month integer,
            day integer
        );
        CREATE TABLE if not exists ticket_details (
            number integer,
            project string,
            details string
        );
        create index if not exists entry_sheet on entry (sheet);
        create index if not exists entry_start_time on entry (start_time);
        create index if not exists entry_end_time on entry (end_time);
        commit;
        ''')
        self.db.execute(u'''
        select
            count(*)
        from
            meta
        where
            key = 'current_sheet'
        ''')
        count = self.db.fetchone()[0]
        if count == 0:
            self.db.execute(u'''
            insert into meta (
                key, value
            ) values (
                'current_sheet', 'default'
            )''')
        self.db.execute(u'''
        select
            count(*)
        from
            meta
        where
            key = 'db_version'
        ''')
        count = self.db.fetchone()[0]
        if count == 0:
            self.db.execute(u'''
                    insert into meta (
                        key, value
                    ) values (
                        'db_version',
                        0
                    );
                ''')
