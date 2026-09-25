"""The default query window has to follow the clock, in UTC.

It stopped doing that in two places, for the same underlying reason: the window
was computed once, at import, and then never again.

``RequestParams`` spelled its bounds as literals evaluated at class-definition
time -- a fixed week in November 2025, which went stale the moment the calendar
moved past it and could not recover. The Dash page built its ``layout`` once at
import too, so ``date.today()`` froze at server start: the hosted app showed the
window as it stood on deploy day and drifted further from the present every day
the process stayed up.

The end bound is tomorrow rather than today because USGS reads both dates as
00:00 UTC and so excludes the end date itself. A window ending today would drop
today's events.
"""
import dataclasses
from datetime import date, datetime, timedelta, timezone

import pandas as pd
from dash import Dash

from earthquake_dashboard import data_loader
from earthquake_dashboard.data_loader import (
    DEFAULT_WINDOW_DAYS,
    DT_FORMAT,
    RequestParams,
    default_window,
    utc_today,
)

# dash.register_page refuses to run before an app exists, and the page module
# calls it at import, so an app has to exist first. pages_folder='' turns off the
# auto-discovery that would then import the same page a second time.
Dash(__name__, use_pages=True, pages_folder='')

from earthquake_dashboard.pages import dashboard  # noqa: E402


def test_the_window_ends_tomorrow_so_that_today_is_included():
    _, end = default_window()
    assert datetime.strptime(end, DT_FORMAT).date() == utc_today() + timedelta(days=1)


def test_the_window_starts_a_month_back():
    # The literal, not DEFAULT_WINDOW_DAYS: reusing the constant on both sides
    # makes the test agree with whatever the window happens to be, and a month
    # is the documented default, not an implementation detail.
    assert DEFAULT_WINDOW_DAYS == 30
    start, _ = default_window()
    assert datetime.strptime(start, DT_FORMAT).date() == utc_today() - timedelta(days=30)


def test_both_bounds_land_on_midnight():
    # USGS reads a bare date as 00:00 UTC, and the widgets say so in their help
    # text; the window the loader sends has to mean the same thing.
    for bound in default_window():
        assert datetime.strptime(bound, DT_FORMAT).time() == datetime.min.time()


def test_the_day_is_read_in_utc_not_in_the_server_zone(monkeypatch):
    """The hour of the day when a host behind UTC disagrees about the date.

    date.today() is the host's local day, and every date this app shows or sends
    is UTC. Pinned against a frozen clock rather than by comparing utc_today()
    to its own body: that comparison restates the implementation, so it holds
    for date.today() too on any host whose clock is already UTC -- which is
    every CI runner this project uses.
    """
    utc_moment = datetime(2030, 3, 11, 1, 30, tzinfo=timezone.utc)
    # A fixed offset rather than a named zone: no tzdata to be missing, and the
    # only thing that matters is being far enough behind UTC to still be on the
    # 10th. Eastern daylight time, as it happens.
    local = timezone(timedelta(hours=-4))

    class FrozenClock(datetime):
        @classmethod
        def now(cls, tz=None):
            return utc_moment if tz else utc_moment.astimezone(local).replace(tzinfo=None)

    monkeypatch.setattr(data_loader, 'datetime', FrozenClock)

    # The premise: at this instant the two zones name different days.
    assert FrozenClock.now().date() == date(2030, 3, 10)
    assert utc_today() == date(2030, 3, 11)


def test_request_params_reads_the_clock_once_per_instance():
    """A plain default is evaluated at class definition and then frozen."""
    fields = {f.name: f for f in dataclasses.fields(RequestParams)}
    for name in ('starttime', 'endtime'):
        field = fields[name]
        assert field.default is dataclasses.MISSING, (
            f'{name} has the fixed default {field.default!r}, so it is computed '
            'once at import and goes stale'
        )
        assert field.default_factory is not dataclasses.MISSING


def test_request_params_defaults_to_the_default_window():
    params = RequestParams()
    assert (params.starttime, params.endtime) == default_window()


def test_request_params_follows_the_clock(monkeypatch):
    monkeypatch.setattr(data_loader, 'utc_today', lambda: date(2030, 3, 10))
    params = RequestParams()
    assert params.starttime == '2030-02-08 00:00:00'
    assert params.endtime == '2030-03-11 00:00:00'


def walk(node):
    """Every component in a Dash component tree, parents before children."""
    yield node
    children = getattr(node, 'children', None)
    if isinstance(children, (list, tuple)):
        for child in children:
            yield from walk(child)
    elif children is not None:
        yield from walk(children)


def date_picker(tree):
    """The date range picker inside a rendered page."""
    pickers = [c for c in walk(tree) if getattr(c, 'id', None) == 'date_range_picker']
    assert len(pickers) == 1, f'expected one date picker, found {len(pickers)}'
    return pickers[0]


def test_the_dash_layout_is_built_per_page_load():
    """A module-level layout object freezes the picker at server start."""
    assert callable(dashboard.layout), (
        'layout is a fixed component tree, so date.today() runs once when the '
        'process starts and the picker shows the deploy day from then on'
    )


def test_the_dash_picker_shows_todays_window(monkeypatch):
    monkeypatch.setattr(dashboard, 'utc_today', lambda: date(2030, 3, 10))
    picker = date_picker(dashboard.layout())
    assert picker.start_date == date(2030, 2, 8)
    assert picker.end_date == date(2030, 3, 11)


def test_the_dash_picker_moves_with_the_day(monkeypatch):
    # Two renders of the same process, a year apart: the second must not still
    # be showing the first one's window.
    monkeypatch.setattr(dashboard, 'utc_today', lambda: date(2030, 3, 10))
    first = date_picker(dashboard.layout()).end_date
    monkeypatch.setattr(dashboard, 'utc_today', lambda: date(2031, 1, 1))
    second = date_picker(dashboard.layout()).end_date
    assert (first, second) == (date(2030, 3, 11), date(2031, 1, 2))


def test_the_table_hides_the_event_url():
    """The URL rides along in the frame for the map's link, not for the table.

    A full USGS event URL is about sixty characters and the table's cells wrap,
    so showing it turns every row three lines tall and squeezes the columns
    somebody is actually reading.
    """
    df = pd.DataFrame({'place': ['x'], 'url': ['https://earthquake.usgs.gov/x'],
                       'mag': [1.0]})
    ids = [c['id'] for c in dashboard.table_columns(df)]
    assert ids == ['place', 'mag']
