from ConfigParser import NoSectionError, NoOptionError
import datetime
import hashlib
import json
import logging
import subprocess
from functools import wraps

from flask import Flask, render_template, request

from timebook import get_best_user_guess, CONFIG_FILE, \
        LOGS, logger, TIMESHEET_DB, TimesheetRow, ChiliprojectLookupHelper
from timebook.db import Database
from timebook.dbutil import date_is_untracked
from timebook.config import parse_config

app = Flask(__name__)

@app.template_filter('md5')
def reverse_filter(s):
    return hashlib.md5(s).hexdigest()

def get_human_username(guess):
    """
    Will check with the passwd database to see if a full name is available
    for the current user.  If one is, it will return that, otherwise, it will
    return the current username.
    """
    try:
        process = subprocess.Popen(["getent", "passwd", guess], stdout = subprocess.PIPE)
        process_data = process.communicate()
        user_info_string = process_data[0]
        if user_info_string:
            user_info = user_info_string.split(":")
            user_details = user_info[4].split(",")
            if(user_details[0]):
                return user_details[0]
        return guess
    except OSError:
        return None

def gather_information(view_func, *args, **kwargs):
    """Returns a valid database session for performing queries."""
    @wraps(view_func)
    def _wrapped_view_func(*args, **kwargs):
        user = get_best_user_guess()
        human_username = get_human_username(user)
        cursor = Database(
                    TIMESHEET_DB,
                    CONFIG_FILE
                )
        config = parse_config(CONFIG_FILE)
        config.add_section('temp')
        config.set('temp', 'human_name', human_username)
        return view_func(cursor, config, *args, **kwargs)
    return _wrapped_view_func

@app.route("/posttest/", methods=["POST",])
@gather_information
def posttest(cursor, config):
    user = request.form.get('user')
    command = request.form.get('command')
    since = request.form.get('since')
    current = request.form.get('current')
    try:
        args = json.loads(request.form.get('args'))
    except TypeError:
        args = [];
    return "DATA RECEIVED: %s [%s since %s] %s(%s)" % (
                user, 
                current,
                since,
                command,
                json.dumps(args),
            )

@app.route("/charts/")
@gather_information
def billable(cursor, config):
    start = request.args.get('start', (datetime.datetime.now() - datetime.timedelta(days = 30)).strftime("%Y-%m-%d"))
    end = request.args.get('end', datetime.datetime.now().strftime("%Y-%m-%d"))
    project = request.args.getlist('project')

    select_constraint = ''
    if start:
        select_constraint = select_constraint + " AND start_time > STRFTIME('%%s', '%s', 'utc') " % start
    if end:
        select_constraint = select_constraint + " AND start_time < STRFTIME('%%s', '%s', 'utc', '1 day') " % end
    if project:
        project_constraints = []
        for p in project:
            project_constraints.append(" project = '%s' " % p)
        project_constraint = " OR ".join(project_constraints)
        select_constraint = select_constraint + " AND ( %s ) " % project_constraint

    logger.info(select_constraint)

    billable_by_day_sql = """
        SELECT
            date,
            ROUND(SUM(CASE WHEN entry.billable = 1 THEN entry.duration ELSE 0 END) / CAST(SUM(entry.duration) AS FLOAT) * 100, 1)
        FROM (
            SELECT 
                billable,
                STRFTIME('%Y-%m-%d', start_time, 'unixepoch', 'localtime') AS date,
                end_time - start_time as duration
            FROM entry
            INNER JOIN entry_details ON entry_details.entry_id = entry.id
            LEFT JOIN ticket_details ON entry_details.ticket_number = ticket_details.number
            WHERE sheet = 'default' """ + (select_constraint if select_constraint else "") + """
        ) AS entry
        GROUP BY date
        ORDER BY date
    """
    billable_by_day_raw = cursor.execute(billable_by_day_sql).fetchall()
    billable_by_day = []
    prev_date = False
    for row in billable_by_day_raw:
        this_date = row[0]
        while prev_date and prev_date != (datetime.datetime.strptime(this_date, "%Y-%m-%d") - datetime.timedelta(days = 1)).strftime("%Y-%m-%d"):
            prev_date_object = (datetime.datetime.strptime(prev_date, "%Y-%m-%d") + datetime.timedelta(days = 1))
            prev_date = prev_date_object.strftime("%Y-%m-%d")
            if 0 < int(datetime.datetime.strptime(prev_date, "%Y-%m-%d").strftime("%w")) < 6:
                if not date_is_untracked(cursor, prev_date_object.year, prev_date_object.month, prev_date_object.day):
                    billable_by_day.append([prev_date, 0])
        billable_by_day.append(row)
        prev_date = row[0]

    all_client_list = cursor.execute("""
        SELECT distinct project FROM ticket_details
        """).fetchall()

    client_list = cursor.execute("""
        SELECT distinct project FROM ticket_details
        INNER JOIN entry_details ON entry_details.ticket_number = ticket_details.number
        INNER JOIN entry ON entry_details.entry_id = entry.id
        WHERE sheet = 'default' """ + ( select_constraint if select_constraint else "") + """
        ;
    """).fetchall()
    if client_list:
        per_client_sql_array = [];
        per_client_sql_array.append("""
                COALESCE(ROUND(SUM(entry.duration), 1), 0) AS total
            """)
        for client in client_list:
            per_client_sql_array.append("""
                SUM(CASE WHEN project = '%s' THEN entry.duration ELSE 0 END) AS '%s'
            """ % (client[0], client[0], ))
        per_client_sql = ", ".join(per_client_sql_array)
        client_by_day_sql = """
            SELECT
                date,
                %s
            FROM (
            SELECT 
                ticket_details.project,
                STRFTIME('%%Y-%%m-%%d', start_time, 'unixepoch', 'localtime') AS date,
                ROUND(SUM((COALESCE(end_time, STRFTIME('%%s', 'now')) - start_time)/ CAST(3600 AS FLOAT)), 1) as duration
            FROM entry
            LEFT JOIN entry_details ON entry_details.entry_id = entry.id
            LEFT JOIN ticket_details ON entry_details.ticket_number = ticket_details.number
            WHERE sheet = 'default' """ + (select_constraint.replace("%", "%%") if select_constraint else '') + """
            GROUP BY STRFTIME('%%Y-%%m-%%d', start_time, 'unixepoch', 'localtime'), ticket_details.project
            ) AS entry
            GROUP BY date
            ORDER BY date
        """;
        client_by_day_sql = client_by_day_sql % per_client_sql
        client_by_day = cursor.execute(client_by_day_sql).fetchall()
        client_by_day_json_arr = [];
        prev_date = False
        for c in client_by_day:
            logging.info(c)
            this_date = c[0]
            while prev_date and prev_date != (datetime.datetime.strptime(this_date, "%Y-%m-%d") - datetime.timedelta(days = 1)).strftime("%Y-%m-%d"):
                prev_date_object = (datetime.datetime.strptime(prev_date, "%Y-%m-%d") + datetime.timedelta(days = 1))
                prev_date = prev_date_object.strftime("%Y-%m-%d")
                if 0 < int(datetime.datetime.strptime(prev_date, "%Y-%m-%d").strftime("%w")) < 6:
                    if not date_is_untracked(cursor, prev_date_object.year, prev_date_object.month, prev_date_object.day):
                        day_arr = [prev_date]
                        day_arr.append(0)
                        for client in client_list:
                            day_arr.append(0)
                        client_by_day_json_arr.append(json.dumps(day_arr))
            client_by_day_json_arr.append(json.dumps(c))
            prev_date = c[0]
    else:
        client_by_day_json_arr = []

    return render_template("dailygraph.html",
                billable_data = billable_by_day,
                all_client_list = all_client_list,
                client_list = client_list,
                client_by_day = client_by_day_json_arr,
                start = start,
                end = end,
                project = project
            )

@app.route("/")
@gather_information
def index(cursor, config):
    current_row = cursor.execute("""
        SELECT 
            id,
            start_time,
            end_time, 
            description, 
            ROUND((COALESCE(end_time, strftime('%s', 'now')) - start_time) / CAST(3600 AS FLOAT), 2) AS hours
        FROM entry 
        WHERE start_time = (select max(start_time) from entry where sheet = 'default')
        """).fetchone()

    todays_tasks_rows = cursor.execute("""
        SELECT
            id, 
            start_time,
            end_time,
            description, 
            ROUND((COALESCE(end_time, strftime('%s', 'now')) - start_time) / CAST(3600 AS FLOAT), 2) AS hours
        FROM entry
        WHERE start_time > strftime('%s', strftime('%Y-%m-%d', 'now', 'localtime'), 'utc') AND sheet = 'default'
        ORDER BY start_time DESC
        """).fetchall()

    lookup_helper = ChiliprojectLookupHelper(db = cursor)
    current = TimesheetRow.from_row(current_row)
    current.set_lookup_handler(lookup_helper)

    hours_total = 0
    todays_tasks = []
    for task_row in todays_tasks_rows:
        task = TimesheetRow.from_row(task_row)
        task.set_lookup_handler(lookup_helper)

        hours_total = hours_total + task.total_hours
        todays_tasks.append(task)

    template_name = "snapshot.html"
    try:
        template_name = config.get('template', 'snapshot')
    except (NoSectionError, NoOptionError):
        pass

    return render_template(template_name, 
            current = current,
            human_username = config.get('temp', 'human_name'),
            todays_tasks = todays_tasks,
            hours_total = hours_total
        )

from logging.handlers import RotatingFileHandler
file_handler = RotatingFileHandler(
    LOGS,
    maxBytes = 2**20,
    backupCount = 1,
)
file_handler.setLevel(logging.DEBUG)
app.logger.addHandler(file_handler)
logger.addHandler(file_handler)
