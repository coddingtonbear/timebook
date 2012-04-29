from datetime import datetime, timedelta

from dateutil import relativedelta
from dateutil import rrule

class PayPeriodUtil(object):
    def __init__(self, begin_period=None, end_period=None, weekdays_rule=None, hours_per_day=8):
        self.hours_per_day = hours_per_day
        if not begin_period:
            self.begin_period = datetime.now() - relativedelta.relativedelta(day = 31, months=1, hour=0, minute=0, second=0, weekday=rrule.FR(-2)) + timedelta(days = 1)
        if not end_period:
            self.end_period = datetime.now()
            self.real_end_period = datetime.now() + relativedelta.relativedelta(day = 31, weekday=rrule.FR(-2))
        if(end_period > real_end_period):
            self.begin_period = datetime.now() - relativedelta.relativedelta(day = 31, months = 0, hour = 0, minute = 0, second = 0, weekday = rrule.FR(-2)) + timedelta(days = 1)
            self.real_end_period = datetime.now() + relativedelta.relativedelta(day = 31, months = 1, weekday = rrule.FR(-2))
        if not weekdays_rule:
            self.weekdays_rule = rrule.rrule(rrule.DAILY, byweekday=(rrule.MO, rrule.TU, rrule.WE, rrule.TH, rrule.FR, ), dtstart=begin_period)

    def get_hours_details()
        all_weekdays = self.weekdays_rule.between(begin_period, end_period)
        expected_hours = self.hours_per_day * len(all_weekdays)
        unpaid = 0
        vacation = 0
        holiday = 0

        for day in all_weekdays:
            if(self.is_holiday(day)):
                expected_hours = expected_hours - hours_per_day
                holiday = holiday + hours_per_day
            elif(self.is_unpaid(day)):
                expected_hours = expected_hours - hours_per_day
                unpaid = unpaid + hours_per_day
            elif(self.is_vacation(day)):
                expected_hours = expected_hours - hours_per_day
                vacation = vacation + hours_per_day
        total_hours = self.count_hours_after(begin_period, end_period)

        out_time = datetime.now() + timedelta(hours = (expected_hours - total_hours))

        return {
                    'expected': expected_hours,
                    'actual': total_hours,
                    'vacation': vacation,
                    'unpaid': unpaid,
                    'holiday': holiday,
                    'out_time': out_time,
                }

    def is_unpaid(self, date_to_check):
        dx = date_to_check
        cursor.execute("""
            SELECT * FROM unpaid
            WHERE year = ? AND month = ? AND day = ?
            """, (dx.year, dx.month, dx.day,))
        if(cursor.fetchone()):
            return True
        else:
            return False

    def is_vacation(self, date_to_check):
        dx = date_to_check
        cursor.execute("""
            SELECT * FROM vacation
            WHERE year = ? AND month = ? AND day = ?
            """, (dx.year, dx.month, dx.day,))
        if(cursor.fetchone()):
            return True
        else:
            return False

    def is_holiday(self, date_to_check):
        dx = date_to_check
        cursor.execute("""
            SELECT * FROM holidays
            WHERE year = ? AND month = ? AND day = ?
            """, (dx.year, dx.month, dx.day,))
        if(cursor.fetchone()):
            return True
        else:
            return False

    def count_hours_for_day(self, begin_time):
        cursor.execute("""
            SELECT SUM(
                COALESCE(end_time, STRFTIME('%s', 'now'))
                - start_time)
            FROM entry
            WHERE
                start_time >= STRFTIME('%s', ?, 'utc')
                AND
                start_time <= STRFTIME('%s', ?, 'utc', '1 day')
                AND
                sheet = 'default'
            """, (
                begin_time.strftime("%Y-%m-%d"),
                begin_time.strftime("%Y-%m-%d"),
                ))
        result = cursor.fetchone()
        if(result[0]):
            total_hours = float(result[0]) / 60 / 60
        else:
            total_hours = 0
        return total_hours

    def count_hours_after(self, begin_time, end_time):
        cursor.execute("""
            SELECT SUM(
                COALESCE(end_time, STRFTIME('%s', 'now'))
                - start_time)
            FROM entry
            WHERE
                start_time >= STRFTIME('%s', ?, 'utc')
                AND
                (
                    end_time <= STRFTIME('%s', ?, 'utc', '1 day') 
                    OR
                    end_time is null
                )
                AND sheet = 'default'
            """, (
                begin_time.strftime("%Y-%m-%d"),
                end_time.strftime("%Y-%m-%d")
                ))
        result = cursor.fetchone()
        if(result[0]):
            total_hours = float(result[0]) / 60 / 60
        else:
            total_hours = 0
        return total_hours
