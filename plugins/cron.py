from __future__ import annotations

import datetime
from typing import Any
from typing import overload
from cron_descriptor import CasingTypeEnum, ExpressionDescriptor, FormatException, MissingFieldException
from croniter import CroniterBadCronError, CroniterBadDateError, croniter
from pendulum import DateTime
from pendulum.tz.timezone import Timezone
from airflow.settings import TIMEZONE
from pendulum import DateTime, instance as pendulum_instance
from airflow.compat.functools import cached_property
from airflow.exceptions import AirflowTimetableInvalid
from airflow.utils.dates import cron_presets
from airflow.utils.timezone import make_aware, make_naive

def is_localized(value):
    """
    Determine if a given datetime.datetime is aware.
    The concept is defined in Python's docs:
    http://docs.python.org/library/datetime.html#datetime.tzinfo
    Assuming value.tzinfo is either None or a proper datetime.tzinfo,
    value.utcoffset() implements the appropriate logic.
    """
    xx = value.utcoffset()
    rs = xx is not None
    return rs

@overload
def convert_to_utc(value: None) -> None:
    ...


@overload
def convert_to_utc(value: datetime.datetime) -> DateTime:
    ...


def convert_to_utc(value: datetime.datetime | None) -> DateTime | None:
    """
    Returns the datetime with the default timezone added if timezone
    information was not associated
    :param value: datetime
    :return: datetime with tzinfo
    """
    from pendulum.tz import timezone
    utc = timezone('UTC')
    if value is None:
        return value

    if not is_localized(value):
        value = pendulum_instance(value, TIMEZONE)

    return pendulum_instance(value.astimezone(utc))

def _is_schedule_fixed(expression: str) -> bool:
    """Figures out if the schedule has a fixed time (e.g. 3 AM every day).

    :return: True if the schedule has a fixed time, False if not.

    Detection is done by "peeking" the next two cron trigger time; if the
    two times have the same minute and hour value, the schedule is fixed,
    and we *don't* need to perform the DST fix.

    This assumes DST happens on whole minute changes (e.g. 12:59 -> 12:00).
    """
    cron = croniter(expression)
    next_a = cron.get_next(datetime.datetime)
    next_b = cron.get_next(datetime.datetime)
    return next_b.minute == next_a.minute and next_b.hour == next_a.hour


class CronMixin:
    """Mixin to provide interface to work with croniter."""

    def __init__(self, cron: str, timezone: str | Timezone) -> None:
        self._expression = cron_presets.get(cron, cron)

        if isinstance(timezone, str):
            timezone = Timezone(timezone)
        self._timezone = timezone

        descriptor = ExpressionDescriptor(
            expression=self._expression, casing_type=CasingTypeEnum.Sentence, use_24hour_time_format=True
        )
        try:
            # checking for more than 5 parameters in Cron and avoiding evaluation for now,
            # as Croniter has inconsistent evaluation with other libraries
            if len(croniter(self._expression).expanded) > 5:
                raise FormatException()
            interval_description = descriptor.get_description()
        except (CroniterBadCronError, FormatException, MissingFieldException):
            interval_description = ""
        self.description = interval_description

    def __eq__(self, other: Any) -> bool:
        """Both expression and timezone should match.

        This is only for testing purposes and should not be relied on otherwise.
        """
        if not isinstance(other, type(self)):
            return NotImplemented
        return self._expression == other._expression and self._timezone == other._timezone


    @property
    def summary(self) -> str:
        return self._expression


    def validate(self) -> None:
        try:
            croniter(self._expression)
        except (CroniterBadCronError, CroniterBadDateError) as e:
            raise AirflowTimetableInvalid(str(e))


    @cached_property
    def _should_fix_dst(self) -> bool:
        # This is lazy so instantiating a schedule does not immediately raise
        # an exception. Validity is checked with validate() during DAG-bagging.
        return not _is_schedule_fixed(self._expression)

    def _get_next(self, current: DateTime) -> DateTime:
        """Get the first schedule after specified time, with DST fixed."""
        naive = make_naive(current, self._timezone)
        cron = croniter(self._expression, start_time=naive)
        scheduled = cron.get_next(datetime.datetime)
        if not self._should_fix_dst:
            return convert_to_utc(make_aware(scheduled, self._timezone))
        delta = scheduled - naive
        tmp = current.in_timezone(self._timezone) + delta
        rs = convert_to_utc(tmp)
        return rs

    def _get_prev(self, current: DateTime) -> DateTime:
        """Get the first schedule before specified time, with DST fixed."""
        naive = make_naive(current, self._timezone)
        cron = croniter(self._expression, start_time=naive)
        scheduled = cron.get_prev(datetime.datetime)
        if not self._should_fix_dst:
            return convert_to_utc(make_aware(scheduled, self._timezone))
        delta = naive - scheduled
        return convert_to_utc(current.in_timezone(self._timezone) - delta)

    def _align_to_next(self, current: DateTime) -> DateTime:
        """Get the next scheduled time.

        This is ``current + interval``, unless ``current`` falls right on the
        interval boundary, when ``current`` is returned.
        """
        next_time = self._get_next(current)
        if self._get_prev(next_time) != current:
            return next_time
        return current

    def _align_to_prev(self, current: DateTime) -> DateTime:
        """Get the prev scheduled time.

        This is ``current - interval``, unless ``current`` falls right on the
        interval boundary, when ``current`` is returned.
        """
        prev_time = self._get_prev(current)
        if self._get_next(prev_time) != current:
            return prev_time
        return current