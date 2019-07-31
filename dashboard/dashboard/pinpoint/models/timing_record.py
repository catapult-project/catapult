# Copyright 2019 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

from __future__ import print_function
from __future__ import division
from __future__ import absolute_import

import datetime

from google.appengine.ext import ndb
from dashboard.common import math_utils


FETCH_LIMIT = 500


class TimingRecord(ndb.Model):
  started = ndb.DateTimeProperty(indexed=False, required=True)
  completed = ndb.DateTimeProperty(indexed=True, required=True)
  tags = ndb.StringProperty(indexed=True, repeated=True)


def GetSimilarHistoricalTimings(job):
  """Gets historical timing data for similar jobs.

  This returns historical data for jobs run on Pinpoint previously, with
  arguments that are similar to specified job.

  Returns a tuple ((median, std_dev, 90th percentil), matching_tags) if similar
  jobs were found, otherwise None.

  Arguments:
  - job: a job entity instance.
  """
  tags = _JobTags(job)

  return _Estimate(tags)


def RecordJobTiming(job):
  tags = _JobTags(job)

  e = TimingRecord(
      id=job.job_id, started=job.started_time, completed=job.updated, tags=tags)
  e.put()


def _JobTags(job):
  tags = [
      _ComparisonMode(job), job.configuration,
      job.arguments.get('benchmark', ''),
      job.arguments.get('story', '')
  ]

  tags = [t for t in tags if t]

  return tags


def _ComparisonMode(job):
  cmp_mode = job.comparison_mode
  if not cmp_mode:
    cmp_mode = 'try'
  return cmp_mode


def _Estimate(tags):
  records = _QueryTimingRecords(tags)

  if not records:
    if tags:
      return _Estimate(tags[:-1])
    return None

  times = [(r.completed - r.started).total_seconds() for r in records]

  median = math_utils.Median(times)
  std_dev = math_utils.StandardDeviation(times)
  p90 = math_utils.Percentile(times, 0.9)
  timings = (
      datetime.timedelta(seconds=median),
      datetime.timedelta(seconds=std_dev),
      datetime.timedelta(seconds=p90))

  return (timings, tags)


def _QueryTimingRecords(tags):
  q = TimingRecord.query()
  for t in tags:
    q = q.filter(TimingRecord.tags == t)
  q = q.order(-TimingRecord.completed)

  return q.fetch(limit=FETCH_LIMIT)
