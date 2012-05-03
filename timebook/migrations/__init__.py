import imp
import inspect
import os.path
import re


class MigrationManager(object):
    def __init__(self, db):
        self.db = db

    def _is_unapplied(self, migration_info):
        if self.db.db_version < migration_info['number']:
            return True
        return False

    def _get_migration_classes(self, migration_number, mod_path):
        migrations = []

        mod = imp.load_source(
                'timebook.migrations.migration%s' % migration_number,
                os.path.join(
                    os.path.dirname(
                        __file__
                    ),
                    mod_path,
                )
            )
        members = inspect.getmembers(mod)
        for name, member in members:
            if (
                    inspect.isclass(member)
                    and issubclass(member, Migration)
                    and member.__name__ != Migration.__name__
                ):
                migrations.append(member)
        return migrations

    def _find_migration_modules(self):
        migration_modules = []
        for mod_path in os.listdir(os.path.dirname(
                __file__
            )):
            migration_details = re.match(r'^(\d+)(\D*)\.py$', mod_path)
            if migration_details:
                try:
                    number = int(migration_details.groups()[0])
                    name = migration_details.groups()[1]
                    migrations = self._get_migration_classes(
                                            number,
                                            mod_path
                            )
                    if migrations:
                        migration_modules.append(
                                    {
                                        'name': name,
                                        'number': number,
                                        'migrations': migrations
                                    }
                                )
                except ValueError:
                    pass
        migration_modules = sorted(
                migration_modules,
                key=lambda k: k['number']
            )
        return migration_modules

    def _apply_migration(self, module):
        print "Applying migration #%s (%s)" % (
                    module['number'],
                    module['name'],
                )
        for migration_class in module['migrations']:
            migration = migration_class(self.db)
            migration.run()

        self._register_migration(module)

    def _register_migration(self, module):
        self.db.execute('''
            UPDATE meta SET value = ? WHERE key = 'db_version';
        ''', (module['number'], ))

    def upgrade(self):
        modules = self._find_migration_modules()
        for module in modules:
            if self._is_unapplied(module):
                self._apply_migration(module)


class MigrationException(Exception):
    pass


class Migration(object):
    def __init__(self, db):
        self.db = db

    def run(self):
        raise MigrationException(
                "Run method must be declared in each migration."
            )
