# Copyright 2015 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

"""URL endpoints to show bisect stats."""

import datetime
import json

from dashboard import layered_cache
from dashboard import request_handler
from dashboard import utils

_BISECT_STATS_CACHE_KEY = 'bisect_stats'
_NUM_POINTS_TO_DISPLAY = 52
_BISECT_STAT_SERIES_NAME = ['win', 'linux', 'mac', 'android']


class BisectStatsHandler(request_handler.RequestHandler):
  """URL endpoint to get stats about bisect runs."""

  def get(self):
    """Renders the UI with charts."""
    bisect_stats = layered_cache.GetExternal(_BISECT_STATS_CACHE_KEY)
    if not bisect_stats:
      bisect_stats = {
          'failed': [],
          'completed': []
      }

    series_data = {
        'failed': bisect_stats['failed'],
        'completed': bisect_stats['completed']
    }

    total_series_data = {
        'failed': self._GetTotalBisectRunSeries(bisect_stats['failed']),
        'completed': self._GetTotalBisectRunSeries(bisect_stats['completed'])
    }

    self.RenderHtml('bisect_stats.html', {
        'series_data': json.dumps(series_data),
        'total_series_data': json.dumps(total_series_data),
    })

  def _GetTotalBisectRunSeries(self, series_map):
    """Sums up failed and completed bisect run series.

    Args:
      series_map: Dictionary of series names to list of data series.

    Returns:
      A list of data series.
    """
    cropped_series_list = []
    for key in series_map:
      series = series_map[key]
      cropped_series_list.append(series[len(series) - _NUM_POINTS_TO_DISPLAY:])

    # Sum up series.
    series_map = {}
    for series in cropped_series_list:
      for x_value, y_value in series:
        if x_value not in series_map:
          series_map[x_value] = y_value
        else:
          series_map[x_value] += y_value

    result_list = []
    for key in sorted(series_map):
      result_list.append([key, series_map[key]])
    return result_list


def UpdateBisectStats(bot_name, status):
  """Updates bisect run stat by bot name and status.

  Bisect stats stored in a layered_cache entity have the form below.  Each
  tick is one week and count is the sum of failed or completed bisect runs.

  {
    'failed': {
      bot_name: [[week_timestamp, count], [week_timestamp, count]],
    },
    'completed': {
      bot_name: [[week_timestamp, count], [week_timestamp, count]],
    }
  }

  Args:
    bot_name: Name of the bisect bot.
    status: Bisect status.  Either 'failed' or 'completed'.
  """
  # TODO(chrisphan): Add stats for staled bisect.
  if status not in ['failed', 'completed']:
    return
  series_name = _GetSeriesNameFromBotName(bot_name)
  week_timestamp = _GetLastMondayTimestamp()

  bisect_stats = layered_cache.GetExternal(_BISECT_STATS_CACHE_KEY)
  if not bisect_stats:
    bisect_stats = {
        'failed': {},
        'completed': {},
    }

  series_map = bisect_stats[status]
  if series_name not in series_map:
    series_map[series_name] = [[week_timestamp, 1]]
  else:
    series = series_map[series_name]
    if week_timestamp == series[-1][0]:
      series[-1][1] += 1
    else:
      series.append([week_timestamp, 1])

  layered_cache.SetExternal(_BISECT_STATS_CACHE_KEY, bisect_stats)


def _GetLastMondayTimestamp():
  """Gets timestamp of 00:00 last Monday in milliseconds as an integer."""
  today = datetime.date.today()
  monday = today - datetime.timedelta(days=today.weekday())
  return utils.TimestampMilliseconds(monday)


def _GetSeriesNameFromBotName(bot_name):
  for series_name in _BISECT_STAT_SERIES_NAME:
    if series_name in bot_name:
      return series_name
  return 'other'
