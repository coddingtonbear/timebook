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
from datetime import timedelta

from dateutil import relativedelta, rrule


class PayPeriod(object):
    def __init__(self, now):
        self.now = now

    @property
    def begin_period(self):
        raise ValueError()

    @property
    def end_period(self):
        raise ValueError()

    @property
    def weekdays_rule(self):
        return rrule.rrule(
            rrule.DAILY,
            byweekday=(
                rrule.MO, rrule.TU, rrule.WE, rrule.TH, rrule.FR,
            ),
            dtstart=self.begin_period,
        )

    @property
    def hours_per_day(self):
        return 8


class RollingWindowPayPeriod(PayPeriod):
    window_size = None

    @property
    def begin_period(self):
        return self.now - relativedelta.relativedelta(
            days=self.window_size,
            hour=0,
            minute=0,
            second=0,
            microsecond=0,
        )

    @property
    def end_period(self):
        return self.now + relativedelta.relativedelta(
            days=1,
            hour=0,
            minute=0,
            second=0,
            microsecond=0,
        )


class Rolling7DayWindow(RollingWindowPayPeriod):
    window_size = 7


class Rolling30DayWindow(RollingWindowPayPeriod):
    window_size = 30


class Rolling90DayWindow(RollingWindowPayPeriod):
    window_size = 90


class RollingAnnualWindow(RollingWindowPayPeriod):
    window_size = 365


class MonthlyOnSecondToLastFriday(PayPeriod):
    @property
    def begin_period(self):
        return self.now - relativedelta.relativedelta(
            day=31,
            months=1,
            hour=0,
            minute=0,
            second=0,
            microsecond=0,
            weekday=rrule.FR(-2)
        ) + timedelta(days = 1)

    @property
    def end_period(self):
        return self.now + relativedelta.relativedelta(
            months=0,
            day=31,
            hour=0,
            minute=0,
            second=0,
            microsecond=0,
            weekday=rrule.FR(-2)
        ) + timedelta(days=1)


class TodayOnly(PayPeriod):
    @property
    def begin_period(self):
        return self.now - relativedelta.relativedelta(
            days=0,
            hour=0,
            minute=0,
            second=0,
            microsecond=0
        )

    @property
    def end_period(self):
        return self.now + relativedelta.relativedelta(
            days=1,
            hour=0,
            minute=0,
            second=0,
            microsecond=0,
        )
