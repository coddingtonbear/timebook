from timebook.migrations import Migration


class TicketMetadataMigration(Migration):
    def run(self):
        self.db.executescript(u'''
        begin;
        create table if not exists entry_meta(
            entry_id integer not null,
            key varchar(16) not null,
            value varchar(256) not null
        );
        commit;
        ''')
