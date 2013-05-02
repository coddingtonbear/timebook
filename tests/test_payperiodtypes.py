from datetime import datetime
import unittest

from ddt import ddt, data

from timebook import payperiodtypes


@ddt
class TestPayPeriodCalculations(unittest.TestCase):
    @data(
        (
            datetime(2013, 5, 1),
            datetime(2013, 4, 1),
            datetime(2013, 5, 2),
        ),
        (
            datetime(2013, 4, 28),
            datetime(2013, 3, 29),
            datetime(2013, 4, 29),
        ),
    )
    def test_rolling_30_day_window_calculations(self, value):
        date, begin_period, end_period = value
        instance = payperiodtypes.Rolling30DayWindow(date)
        self.assertEquals(
            instance.begin_period,
            begin_period
        )
        self.assertEquals(
            instance.end_period,
            end_period
        )

    @data(
        (
            datetime(2013, 5, 1),
            datetime(2013, 4, 20),
            datetime(2013, 5, 25),
        ),
        (
            datetime(2013, 4, 18),
            datetime(2013, 3, 23),
            datetime(2013, 4, 20),
        ),
    )
    def test_monthly_on_second_to_last_friday_calculations(self, value):
        date, begin_period, end_period = value
        instance = payperiodtypes.MonthlyOnSecondToLastFriday(date)
        self.assertEquals(
            instance.begin_period,
            begin_period
        )
        self.assertEquals(
            instance.end_period,
            end_period
        )
