import logging
import subprocess
from functools import wraps

from flask import Flask, render_template

from timebook import get_best_user_guess, CONFIG_FILE, \
        LOGS, logger, TIMESHEET_DB, TimesheetRow, ChiliprojectLookupHelper
from timebook.db import Database

app = Flask(__name__)

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
        return view_func(cursor, human_username, *args, **kwargs)
    return _wrapped_view_func

@app.route("/balance/")
@gather_information
def balance(cursor, human_username):
    return ""

@app.route("/")
@gather_information
def index(cursor, human_username):
    current_row = cursor.execute("""
        SELECT 
            id,
            start_time,
            end_time, 
            description, 
            ROUND((COALESCE(end_time, strftime('%s', 'now')) - start_time) / CAST(3600 AS FLOAT), 2) AS hours
        FROM entry 
        WHERE start_time = (select max(start_time) from entry);
        """).fetchone()

    todays_tasks_rows = cursor.execute("""
        SELECT
            id, 
            start_time,
            end_time,
            description, 
            ROUND((COALESCE(end_time, strftime('%s', 'now')) - start_time) / CAST(3600 AS FLOAT), 2) AS hours
        FROM entry
        WHERE start_time > strftime('%s', strftime('%Y-%m-%d', 'now', 'localtime'), 'utc')
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

    return render_template("snapshot.html", 
            current = current,
            human_username = human_username,
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
