.. -*- restructuredtext -*-

Timebook
========

Timebook is a small utility which aims to be a low-overhead way of
tracking what you spend time on. It can be used to prepare annotated
time logs of work for presentation to a client, or simply track how you
spend your free time. Timebook is implemented as a python script which
maintains its state in a sqlite3 database.

Concepts
~~~~~~~~

Timebook maintains a list of *timesheets* -- distinct lists of timed
*periods*. Each period has a start and end time, with the exception of the
most recent period, which may have no end time set. This indicates that
this period is still running. Timesheets containing such periods are
considered *active*. It is possible to have multiple timesheets active
simultaneously, though a single time sheet may only have one period
running at once.

Interactions with timebook are performed through the ``t`` command on
the command line. ``t`` is followed by one of timebook's subcommands.
Often used subcommands include ``in``, ``out``, ``switch``, ``now``,
``list`` and ``display``. Commands may be abbreviated as long as they
are unambiguous: thus ``t switch foo`` and ``t s foo`` are identical.
With the default command set, no two commands share the first same
letter, thus it is only necessary to type the first letter of a command.
Likewise, commands which display timesheets accept abbreviated timesheet
names. ``t display f`` is thus equivalent to ``t display foo`` if
``foo`` is the only timesheet which begins with "f". Note that this does
not apply to ``t switch``, since this command also creates timesheets.
(Using the earlier example, if ``t switch f`` is entered, it would thus
be ambiguous whether a new timesheet ``f`` or switching to the existing
timesheet ``foo`` was desired).

Usage
~~~~~

The basic usage is as follows::

  $ t in 'document timebook'
  $ t change 'doing something else'
  $ t out

The first command, ``t in 'document timebook'`` creates a new period in
the current timesheet, and annotates it with the description "document
timebook". The second, ``t change 'doing something else'`` ends the first period
you created a moment ago, and starts a new period, annotating it with the 
description 'doing something else'.  Finally, ``t out`` records the current
time as the end time for the most recent period in the ``writing``
timesheet.

To display the current timesheet, invoke the ``t display`` command::

  $ t display
  Timesheet writing:
  Day            Start      End        Duration   Notes
  Mar 14, 2009   19:53:30 - 20:06:15   0:12:45    document timebook
                 20:07:02 -            0:00:01    write home about timebook
                                       0:12:46
  Total                                0:12:46

Each period in the timesheet is listed on a row. If the timesheet is
active, the final period in the timesheet will have no end time. After
each day, the total time tracked in the timesheet for that day is
listed. Note that this is computed by summing the durations of the
periods beginning in the day. In the last row, the total time tracked in
the timesheet is shown.

Parthenon-Related Usage
~~~~~~~~~~~~~~~~~~~~~~~

Annotating work-related projects can be somewhat more complicated due to having
specific projects associated with billable or non-billable tickets, but
timebook will help make this reasonably easy for you by allowing you to specify,
in addition to a description, a ticket number that will be used when posting your
timesheet (you can change 'in' to 'change' should you be switching tasks instead
of starting a new one)::

  $ t in --ticket=1038 "Working on my falafel recipe"

The above command will enter 'Working on my falafel recipe' into your timesheet,
set the entry's ticket number to '1038' and mark the task as billable (the default).
But, what if you want your ticket to be marked as non-billable? ::

  $ t in --ticket=1038 --non-billable "Working on my falafel recipe"

Additionally, you can modify previous entries' ticket number and billable status
(as well as any custom attributes) by using the ``alter`` command, optionally
providing the ID number of an entry of which you'd like to change the properties. ::

  $ t alter --id=208 --ticket=2408

At the end of the day, you can post your hours to our timesheet automatically
by running::

  $ t post

If you do not have your credentials saved in the configuration, you will
be asked for your username and password, statistics will be gathered (if
possible) for the entries you are posting, and your entries will be posted
to your timesheet online.

Web Interface
~~~~~~~~~~~~~

A web interface for viewing timebook information is available in the project
``timebook_web``; head over to http://bitbucket.org/latestrevision/timebook_web/
for details.

Configuration
~~~~~~~~~~~~~

A configuration file lives in ``~/.config/timebook/timebook.ini`` that you can 
use to configure various options in the timebook application including setting
your ChiliProject username and password.

If you'd like to not be asked for your username and password when you're posting
a timesheet and/or allow the web interface to gather information from ChiliProject
directly, you can enter your username and password inside the above file in
a format like::

  [auth]
  username = MY USERNAME
  password = MY PASSWORD

Additionally, you can set sheet-specific reporting urls and hooks by setting
a configuration section using the name of the sheet for which you would like
a pre, post, or reporting hook to be executed, and the name of the URL or 
application you would like executed like::
    
  [default]
  post_hook = /path/to/some/application
  pre_hook = /path/to/some/other/application
  reporting_url = http://www.somedomain.com/reporting/

In the event that you would like your hours to be automatically posted when
you run ``t out``, you can enter a configuration key like the following::

  [automation]
  post_on_clockout = True


Custom Metadata
---------------

You might have a peculiar use for storing some specific bit of metadata about
individual ticket entries.  You can use custom metadata attributes to provide
this functionality.

To use custom metadata attributes, create a configuration section named 
``custom_ticket_meta`` with the keys and values named after the name of the
attribute and its help text, respectively::

  [custom_ticket_meta]
  with=Who are you working with right now?
  category=What category is the work you're working on?

This will add two new parameters that are settable and modifiable during your 
``t in``, ``t change`` and ``t alter`` commands just like built-in attributes 
like an entry's associated ticket number and billable status.

Command Aliases
---------------

You will quickly notice that there are rather a lot of commands and that the
connection between the command name and its action may be entirely unclear 
to you; in order to allow one to use the system in a way that suits their cognitive
processes best, you are able to specify aliases for any command.

For example, if you would prefer to use the command ``to`` instead of ``change``
when changing tasks , you can create aliases in an
``aliases`` section in your Timebook configuration. ::

  [aliases]
  to=change

You can also override built-in commands; so if you rarely use the built-in ``switch``
command and would rather have it behave as ``change`` already does, you can, of course,
do that, too.


Commands
~~~~~~~~

**alter**
  Inserts a note associated with the currently active period in the
  timesheet.

  *Also accepts custom ticket metadata parameters.*

  usage: ``t alter [--billable] [--non-billable] [--ticket=TICKETNUMBER] [--id=ID] NOTES...``

  aliases: *write*

**backend**
  Run an interactive database session on the timebook database. Requires
  the sqlite3 command.

  usage: ``t backend``

  aliases: *shell*

**change**
  Stop the timer for the current timesheet, and re-start the timer for the
  current timesheet with a new description.  Notes may be specified for this 
  period. This is roughly equivalent to ``t out; t in NOTES``, excepting that
  any metadata set for the previous timesheet entry will be preserved for the
  new timesheet entry.

  *Also accepts custom ticket metadata parameters.*

  usage: ``t change [--billable] [--non-billable] [--ticket=TICKETNUMBER] [NOTES...]``

**details**
  Displays details regarding tickets assigned to a specified ticket number.

  Information displayed includes the project name and ticket title, as well
  as the number of hours attributed to the specified ticket and the billable
  percentage.

  usage: ``t details TICKET_NUMBER``

**display**
  Display a given timesheet. If no timesheet is specified, show the
  current timesheet.

  Additionally allows one to display the ID#s for individual timesheet
  entries (for making modifications).

  *By default, shows only the last seven days of activity.*

  usage: ``t display [--show-ids] [--start=YYYY-MM-DD] [--end=YYYY-MM-DD] [TIMESHEET]``

  aliases: *show*

**format**
  Export the current sheet as a comma-separated value format
  spreadsheet.  If the final entry is active, it is ignored.

  If a specific timesheet is given, display the same information for
  that timesheet instead.

  usage: ``t format [--start DATE] [--end DATE] [TIMESHEET]``

  aliases: *csv*, *export*

**hours**
  Calculates your timesheet's current balance for the current pay period
  given a 40-hour work week.

  Uses entries in additional tables named *unpaid*, *vacation*, and *holiday*
  to calculate whether a specific day counts as one during which you are
  expecting to reach eight hours.

  usage: ``t hours``

  aliases: *payperiod*, *pay*, *period*, *offset*

**in**
  Start the timer for the current timesheet. Must be called before out.
  Notes may be specified for this period. This is exactly equivalent to
  ``t in; t alter NOTES``

  *Also accepts custom ticket metadata parameters.*

  usage: ``t in [--billable] [--non-billable] [--ticket=TICKETNUMBER] [--switch TIMESHEET] [NOTES...]``

  aliases: *start*

**insert**
  Insert a new entry into the current timesheet.  Times must be in the 
  YYYY-MM-DD HH:MM format, and all parameters should be quoted.

  usage: ``t insert START END NOTE``

**kill**
  Delete a timesheet. If no timesheet is specified, delete the current
  timesheet and switch to the default timesheet.

  usage: ``t kill [TIMESHEET]``

  aliases: *delete*

**list**
  List the available timesheets.

  usage: ``t list``

  aliases: *ls*

**modify**
  Provides a facility for one to modify a previously-entered timesheet entry.

  Requires the ID# of the timesheet entry; please see the command
  named *display* above.

  usage ``t modify ID``

**now**
  Print the current sheet, whether it's active, and if so, how long it
  has been active and what notes are associated with the current period.

  If a specific timesheet is given, display the same information for
  that timesheet instead.

  usage: ``t now [--simple] [TIMESHEET]``

  aliases: *info*

**out**
  Stop the timer for the current timesheet. Must be called after in.

  usage: ``t out [--verbose] [TIMESHEET]``

  aliases: *stop*

**post**
  Posts your current timesheet to our internal hours tracking system.

  The application will not require your input to post hours if you have stored
  your credentials in your configuration, but if you have not, your username
  and password will be requested.

  usage ``t post [--date=YYYY-MM-DD]``

**running**
  Print all active sheets and any messages associated with them.

  usage: ``t running``

  aliases: *active*

**stats**
  Print out billable hours and project time allocation details for the past
  seven days.

  Optionally you can specify the range of time for which you'd like statistics
  calculated.

  usage ``t stats [--start=YYYY-MM-DD] [--end=YYYY-MM-DD]``

**switch**
  Switch to a new timesheet. this causes all future operation (except
  switch) to operate on that timesheet. The default timesheet is called
  "default".

  usage: ``t switch TIMESHEET``
