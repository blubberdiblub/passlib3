#!/usr/bin/env python3

from __future__ import annotations

import calendar
import datetime
import os
import time

from zoneinfo import ZoneInfo

from typing import TYPE_CHECKING
if TYPE_CHECKING:
    from datetime import datetime as DateTime, timedelta as TimeDelta, tzinfo as TZInfo
    from time import struct_time as StructTime


class SystemTZ(datetime.tzinfo):
    """
    A `tzinfo` subclass modeling the system timezone.

    This class allows `datetime` objects to be created containing the local
    timezone information. It inherits from `tzinfo` and is compatible with
    `ZoneInfo` objects.

    You can provide a custom `datetime.datetime` compatible class during
    instantiation to have it return instances of that class rather than
    ordinary `datetime.datetime` objects.

    You can also specify a name for the instance that will be used as return
    values for `obj.__str__()` and `obj.__repr__()` instead of the defaults.

    The key methods are:

    - `fromutc()` - Convert a UTC datetime object to a local datetime object.
    - `utcoffset()` - Return the timezone offset.
    - `tzname()` - Return the timezone name.
    - `dst()` - Return the daylight saving offset.

    The methods pull timezone information from the `time` module rather than
    taking the information as arguments.

    Example:
        >>> tz = SystemTZ()
        >>> str(tz)
        '<SystemTZ>'
    """

    def __init__(
        self,
        datetime_like_cls: type[DateTime] = datetime.datetime,
        *args: object,
        name: str | None = None,
        **kwargs: object,
    ) -> None:
        super().__init__(*args, **kwargs)
        self._DateTime = datetime_like_cls
        self._unix_epoch = self._DateTime(1970, 1, 1, tzinfo=datetime.UTC)
        self._zero_delta = self._unix_epoch - self._unix_epoch
        self._TimeDelta = type(self._zero_delta)
        self._name = str(name) if name else None

    def __str__(self) -> str:
        if self._name:
            return self._name
        return '<' + self.__class__.__name__ + '>'

    def __repr__(self) -> str:
        if self._name:
            return self._name
        args: list[str] = []
        if self._DateTime is not datetime.datetime:
            args.append(self._DateTime.__module__ + '.' + self._DateTime.__qualname__)
        return '{}({})'.format(self.__class__.__qualname__, ', '.join(args))

    def __eq__(self, other: SystemTZ | object) -> bool:
        if other.__class__ is not self.__class__:
            return NotImplemented

        return other._DateTime is self._DateTime

    def fromutc(self, dt: DateTime) -> DateTime:
        """Convert a UTC datetime object to a local datetime object.

        Takes a datetime object that is in UTC time and converts it to the
        local timezone, accounting for daylight savings time if necessary.

        Parameters:
            dt (datetime.datetime): The UTC datetime object to convert.

        Returns:
            datetime.datetime: The datetime converted to the local timezone.

        Example:
            >>> os.environ['TZ'] = 'Europe/Warsaw'
            >>> time.tzset()
            >>> utc_dt = datetime.datetime(2022, 1, 1, 12, 0, 0, tzinfo=datetime.UTC)
            >>> tz = SystemTZ()
            >>> local_dt = utc_dt.astimezone(tz)
            >>> local_dt
            datetime.datetime(2022, 1, 1, 13, 0, tzinfo=SystemTZ())
        """
        assert dt.tzinfo is self

        secs = calendar.timegm((dt.year, dt.month, dt.day, dt.hour, dt.minute, dt.second))
        t = time.localtime(secs)
        args = t[:6]
        if not hasattr(self._DateTime, 'fold'):
            return self._DateTime(*args, microsecond=dt.microsecond, tzinfo=self)

        if t.tm_isdst < 0:
            return self._DateTime(*args, microsecond=dt.microsecond, tzinfo=self, fold=0)
        secs0 = time.mktime((*t[:8], not t.tm_isdst))
        if secs0 >= secs:
            return self._DateTime(*args, microsecond=dt.microsecond, tzinfo=self, fold=0)
        t0 = time.localtime(secs0)
        return self._DateTime(
            *args, microsecond=dt.microsecond, tzinfo=self, fold=int(t.tm_gmtoff < t0.tm_gmtoff)
        )

    def _mktime(self, dt: DateTime) -> tuple[StructTime, float]:
        assert dt.tzinfo is self
        secs = time.mktime((dt.year, dt.month, dt.day, dt.hour, dt.minute, dt.second, 0, 1, -1))
        t = time.localtime(secs)
        if not hasattr(dt, 'fold'):
            return t, secs + dt.microsecond / 1_000_000

        if t.tm_isdst < 0:
            return t, secs + dt.microsecond / 1_000_000

        secs0 = time.mktime((*t[:8], not t.tm_isdst))
        if secs0 == secs:
            return t, secs + dt.microsecond / 1_000_000

        t0 = time.localtime(secs0)
        if t.tm_gmtoff == t0.tm_gmtoff:
            return t, secs + dt.microsecond / 1_000_000

        if (t.tm_gmtoff > t0.tm_gmtoff) ^ bool(dt.fold):
            return t, secs + dt.microsecond / 1_000_000
        return t0, secs0 + dt.microsecond / 1_000_000

    def utcoffset(self, dt: DateTime | None) -> TimeDelta:
        """Return the timezone offset for the given datetime.

        Return the offset for the given datetime by
        calculating the offset between it and UTC.
        If dt is None, return the offset for the current time instead.

        Example:
            >>> os.environ['TZ'] = 'Europe/Amsterdam'
            >>> time.tzset()
            >>> tz = SystemTZ()
            >>> dt = datetime.datetime(2022, 1, 1, 12, 0, 0, tzinfo=tz)
            >>> tz.utcoffset(dt)
            datetime.timedelta(seconds=3600)
        """
        # TODO: investigate if we have to round to whole minutes for Python < 3.6
        if dt is None:
            return self._TimeDelta(seconds=time.localtime().tm_gmtoff)

        return self._TimeDelta(seconds=self._mktime(dt)[0].tm_gmtoff)

    def tzname(self, dt: DateTime | None) -> str:
        """Return the timezone name for the given datetime.

        Return the name of the timezone for the given datetime,
        unless dt is None, in which case return the name for the current time.

        Example:
            >>> os.environ['TZ'] = 'America/New_York'
            >>> time.tzset()
            >>> tz = SystemTZ()
            >>> dt = datetime.datetime(2022, 1, 1, 12, 0, 0, tzinfo=tz)
            >>> tz.tzname(dt)
            'EST'
        """
        if dt is None:
            return time.localtime().tm_zone

        return self._mktime(dt)[0].tm_zone

    def dst(self, dt: DateTime | None) -> TimeDelta | None:
        """Return daylight saving time offset for given datetime.

        This method checks whether DST is in effect for a given datetime. If no
        datetime is provided, it defaults to the current local time. If DST is
        not in effect, it returns a zero duration. If DST is in effect, it
        calculates the DST offset and returns it as a `datetime.timedelta`.

        Example:
            >>> os.environ['TZ'] = 'Australia/Melbourne'
            >>> time.tzset()
            >>> tz = SystemTZ()
            >>> dt = datetime.datetime(2022, 1, 1, 12, 0, 0, tzinfo=tz)
            >>> tz.dst(dt)
            datetime.timedelta(seconds=3600)
        """
        if dt is None:
            secs = time.time()
            t = time.localtime(secs)
        else:
            t, secs = self._mktime(dt)
        if t.tm_isdst < 0:
            return None

        if not t.tm_isdst:
            return self._zero_delta
        secs0 = time.mktime((*t[:8], 0)) + secs % 1
        dstoff = round(secs0 - secs)
        # TODO: investigate if we have to round to whole minutes for Python < 3.6
        return self._TimeDelta(seconds=dstoff)


def get_tzinfo() -> TZInfo:

    if not (tz := os.environ.get('TZ')):
        return SystemTZ()

    tz = tz.removeprefix(':')
    if os.path.isabs(tz):
        with open(tz, mode='rb') as f:
            return ZoneInfo.from_file(f)

    return ZoneInfo(tz)
