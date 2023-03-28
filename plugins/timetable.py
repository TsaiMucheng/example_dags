from typing import Any, Dict, List, Optional
from pendulum import Date, Time, DateTime, Duration, timezone, now, instance as pendulum_instance
from airflow.plugins_manager import AirflowPlugin
from airflow.timetables.base import DagRunInfo, DataInterval, TimeRestriction, Timetable
from airflow.exceptions import AirflowTimetableInvalid
from airflow.serialization.serialized_objects import encode_timezone
from trigger import CronTriggerTimetable
from operator import and_, le
from croniter import croniter
from datetime import timedelta
from functools import reduce
from os import getenv
import logging

# TAIPEI = timezone('Asia/Taipei')

class onworktime(CronTriggerTimetable):
    def __init__(self, cron: str, *, 
        timezone = getenv('AIRFLOW__CORE__DEFAULT_TIMEZONE'), 
        onwork = [8,0,0], 
        offwork = [17,0,0], 
        interval = timedelta(), 
    ):
        super().__init__(cron = cron, timezone = timezone, interval = interval)
        hmslist = lambda time: list(map(int, time.split(':'))) if isinstance(time, str) else time
        self.onwork = hmslist(onwork)# '08:00:00'/ [8,0,0]
        self.offwork = hmslist(offwork)# '17:00:00'/ [17,0,0]
        self.delta = timedelta(days = 1)
        self._tparas = lambda h, m, s: {'hour': h, 'minute': m, 'second': s}

    def in_trigger_time(self, Time:DateTime, low = None, high = None):
        """:Time local timezone"""
        return self._compare(Time, self.onwork, self.offwork)

    def _offsetseconds(self):
        return self._realtimezone().utcoffset(now())

    def _settime(self, Time, *arg):
        """
        :Time local timezone
        """
        return Time.set(**self._tparas(*arg))

    def _compare(self, Time:DateTime, low = None, high = None):
        """:Time local timezone"""
        if not isinstance(Time, DateTime): raise TypeError('Not be `%s` type: %s' % (DateTime.__name__, type(Time).__name__))
        comparelist = []
        notnone = lambda x: x != None
        compare = lambda *arg, op = le: reduce(op, [*arg]) if all(map(notnone, [*arg])) else None
        if low: comparelist.append(compare(self._settime(Time, *low) , Time))
        if high: comparelist.append(compare(Time , self._settime(Time, *high)))
        return reduce(and_, list(filter(notnone, comparelist)))

    def _realtimezone(self):
        return timezone(encode_timezone(self._timezone))

    def utctime(self, time):
        return timezone('UTC').convert(time)

    def realtime(self, time):
        return self._realtimezone().convert(time)

    def next_dagrun_info(
        self,
        *,
        last_automated_data_interval,
        restriction: TimeRestriction,
    ):
        onwork = self.onwork
        logging.debug("Interval of the job: %s" % str(self._interval))
        if restriction.catchup:
            if last_automated_data_interval is None:
                if restriction.earliest is None:
                    return None
                logging.debug("earliest trigger time: %s" % str(restriction.earliest))
                next_start_time = self._align_to_next(restriction.earliest)
            else:
                next_start_time = self._get_next(last_automated_data_interval.end)
        else:
            current_time = DateTime.utcnow()
            if restriction.earliest is not None and current_time < restriction.earliest:
                logging.debug("earliest trigger time: %s" % str(restriction.earliest))
                next_start_time = self._align_to_next(restriction.earliest)
            else:
                next_start_time = self._align_to_next(current_time)
        if restriction.latest is not None and restriction.latest < next_start_time:
            logging.debug("latest trigger - %s less than next trigger - %s" % (str(restriction.latest), str(next_start_time)))
            return None

        # determine if in workday
        next_start_time = self.realtime(next_start_time)
        logging.debug("real datetime with timezone: %s" % str(next_start_time))
        logging.debug("utc datetime with timezone: %s" % str(self.utctime(next_start_time)))
        logging.debug("onwork datetime with timezone: %s" % str(self._settime(next_start_time, *onwork)))
        if self._compare(next_start_time, low = onwork, high = self.offwork):
            next_real_start_time = next_start_time
            logging.debug("It's work time: %s" % str(next_real_start_time))
        elif self._compare(next_start_time, high = onwork):
            logging.debug("It's before work time in this day: %s" % str(next_start_time))
            next_real_start_time = self._settime(next_start_time, *onwork)
            logging.debug("Next work time in this day: %s" % str(next_real_start_time))
        else:
            logging.debug("It's after work time in this day: %s" % str(next_start_time))            
            next_real_start_time = self._settime(next_start_time + self.delta, *onwork)
            logging.debug("Next work time in the other day: %s" % str(next_real_start_time))
        interval = DagRunInfo.interval(
            start = self.utctime(next_start_time - self._interval), 
            end = self.utctime(next_real_start_time)
        )
        return interval

class MultiCronTimetable(Timetable):
    """
    reference by brki
    https://stackoverflow.com/questions/72478492/airflow-timetable-that-combines-multiple-cron-expressions
    """
    valid_units = ['minutes', 'hours', 'days']

    def __init__(self,
                 cron_defs: List[str],
                 timezone: str = 'Asia/Taipei',
                 period_length: int = 0,
                 period_unit: str = 'hours'):

        self.cron_defs = cron_defs
        self.timezone = timezone
        self.period_length = period_length
        self.period_unit = period_unit

    def infer_manual_data_interval(self, run_after: DateTime) -> DataInterval:
        """
        Determines date interval for manually triggered runs.
        This is simply (now - period) to now.
        """
        end = run_after
        if self.period_length == 0:
            start = end
        else:
            start = self.data_period_start(end)
        return DataInterval(start=start, end=end)

    def data_period_start(self, period_end: DateTime):
        return period_end - Duration(**{self.period_unit: self.period_length})
        
    def next_dagrun_info(
        self,
        *,
        last_automated_data_interval: Optional[DataInterval],
        restriction: TimeRestriction) -> Optional[DagRunInfo]:
        """
        Determines when the DAG should be scheduled.

        """

        if restriction.earliest is None:
            # No start_date. Don't schedule.
            return None

        is_first_run = last_automated_data_interval is None

        if is_first_run:
            if restriction.catchup:
                scheduled_time = self.next_scheduled_run_time(restriction.earliest)

            else:
                scheduled_time = self.previous_scheduled_run_time()
                if scheduled_time is None:
                    # No previous cron time matched. Find one in the future.
                    scheduled_time = self.next_scheduled_run_time()
        else:
            last_scheduled_time = last_automated_data_interval.end

            if restriction.catchup:
                scheduled_time = self.next_scheduled_run_time(last_scheduled_time)

            else:
                scheduled_time = self.previous_scheduled_run_time()

                if scheduled_time is None or scheduled_time == last_scheduled_time:
                    # No previous cron time matched,
                    # or the matched cron time was the last execution time,
                    scheduled_time = self.next_scheduled_run_time()

                elif scheduled_time > last_scheduled_time:
                    # Matched cron time was after last execution time, but before now.
                    # Use this cron time
                    pass

                else:
                    # The last execution time is after the most recent matching cron time.
                    # Next scheduled run will be in the future
                    scheduled_time = self.next_scheduled_run_time()

        if scheduled_time is None:
            return None

        if restriction.latest is not None and scheduled_time > restriction.latest:
            # Over the DAG's scheduled end; don't schedule.
            return None

        start = self.data_period_start(scheduled_time)
        return DagRunInfo(run_after=scheduled_time, data_interval=DataInterval(start=start, end=scheduled_time))

    def croniter_values(self, base_datetime=None):
        if not base_datetime:
            tz = timezone(self.timezone)
            base_datetime = now(tz)

        return [croniter(expr, base_datetime) for expr in self.cron_defs]

    def next_scheduled_run_time(self, base_datetime: DateTime = None):
        min_date = None
        tz = timezone(self.timezone)
        if base_datetime:
            base_datetime_localized = base_datetime.in_timezone(tz)
        else:
            base_datetime_localized = now(tz)

        for cron in self.croniter_values(base_datetime_localized):
            next_date = cron.get_next(DateTime)
            if not min_date:
                min_date = next_date
            else:
                min_date = min(min_date, next_date)
        if min_date is None:
            return None
        return pendulum_instance(min_date)

    def previous_scheduled_run_time(self, base_datetime: DateTime = None):
        """
        Get the most recent time in the past that matches one of the cron schedules
        """
        max_date = None
        tz = timezone(self.timezone)
        if base_datetime:
            base_datetime_localized = base_datetime.in_timezone(tz)
        else:
            base_datetime_localized = now(tz)

        for cron in self.croniter_values(base_datetime_localized):
            prev_date = cron.get_prev(DateTime)
            if not max_date:
                max_date = prev_date
            else:
                max_date = max(max_date, prev_date)
        if max_date is None:
            return None
        return pendulum_instance(max_date)


    def validate(self) -> None:
        if not self.cron_defs:
            raise AirflowTimetableInvalid("At least one cron definition must be present")

        if self.period_unit not in self.valid_units:
            raise AirflowTimetableInvalid(f'period_unit must be one of {self.valid_units}')

        if self.period_length < 0:
            raise AirflowTimetableInvalid(f'period_length must not be less than zero')

        try:
            self.croniter_values()
        except Exception as e:
            raise AirflowTimetableInvalid(str(e))

    @property
    def summary(self) -> str:
        """A short summary for the timetable.

        This is used to display the timetable in the web UI. A cron expression
        timetable, for example, can use this to display the expression.
        """
        return ' || '.join(self.cron_defs)
        #  + f' [TZ: {self.timezone}]'

    def serialize(self) -> Dict[str, Any]:
        """Serialize the timetable for JSON encoding.

        This is called during DAG serialization to store timetable information
        in the database. This should return a JSON-serializable dict that will
        be fed into ``deserialize`` when the DAG is deserialized.
        """
        return dict(cron_defs=self.cron_defs,
                    timezone=self.timezone,
                    period_length=self.period_length,
                    period_unit=self.period_unit)

    @classmethod
    def deserialize(cls, data: Dict[str, Any]) -> "MultiCronTimetable":
        """Deserialize a timetable from data.

        This is called when a serialized DAG is deserialized. ``data`` will be
        whatever was returned by ``serialize`` during DAG serialization.
        """
        return cls(**data)

class CustomTimetablePlugin(AirflowPlugin):
    name = "custom_timetable_plugin"
    timetables = [MultiCronTimetable, onworktime]