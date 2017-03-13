# Copyright 2017 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

from google.appengine.ext import ndb


def GetHealthReport(name):
  report = ndb.Key('BenchmarkHealthReport', name).get()
  if not report:
    return None
  return report.GetReport()


class BenchmarkHealthReport(ndb.Model):
  """Ancestor class for a set of BenchmarkHealthData entities."""
  # The time the report was created.
  timestamp = ndb.DateTimeProperty(indexed=True, auto_now_add=True)
  num_days = ndb.IntegerProperty()
  master = ndb.StringProperty()
  # The report is created via several jobs in the task queue. We know how
  # many benchmarks should be created by these jobs. If the report is complete,
  # a query for its children produces expected_num_benchmarks.
  expected_num_benchmarks = ndb.IntegerProperty()

  def GetReport(self):
    benchmarks = BenchmarkHealthData.query(
        ancestor=self.key).fetch()
    complete_benchmarks = [b for b in benchmarks if b.is_complete]
    is_complete = len(complete_benchmarks) == self.expected_num_benchmarks
    return {
        'name': self.key.string_id(),
        'is_complete': is_complete,
        'benchmarks': benchmarks,
        'num_days': self.num_days,
        'timestamp': self.timestamp,
        'master': self.master,
    }


class ReviewData(ndb.Model):
  review_url = ndb.StringProperty()
  bug_id = ndb.IntegerProperty()


class AlertHealthData(ndb.Model):
  """Stores health data about an individual alert."""
  bug_id = ndb.IntegerProperty()
  test_path = ndb.StringProperty()
  percent_changed = ndb.StringProperty()
  absolute_delta = ndb.StringProperty()
  valid = ndb.ComputedProperty(
      lambda self: self.bug_id is not None and self.bug_id > 0)
  invalid = ndb.ComputedProperty(
      lambda self: self.bug_id is not None and self.bug_id < 0)
  untriaged = ndb.ComputedProperty(
      lambda self: self.bug_id is None)


class BugHealthData(ndb.Model):
  bug_id = ndb.IntegerProperty()
  num_comments = ndb.IntegerProperty()
  published = ndb.DateTimeProperty()
  state = ndb.StringProperty()
  status = ndb.StringProperty()
  summary = ndb.StringProperty()


class BisectHealthData(ndb.Model):
  bug_id = ndb.IntegerProperty()
  bot = ndb.StringProperty()
  buildbucket_link = ndb.StringProperty()
  metric = ndb.StringProperty()
  status = ndb.StringProperty()
  reason = ndb.StringProperty()


class BotHealthData(ndb.Model):
  """Stores data about a single bot a benchmark is running on."""
  name = ndb.StringProperty()
  last_update = ndb.DateTimeProperty()
  @ndb.ComputedProperty
  def platform(self):  # pylint: disable=invalid-name
    if 'android' in self.name:
      return 'android'
    if 'win' in self.name:
      return 'windows'
    if 'mac' in self.name:
      return 'mac'
    if 'linux' in self.name:
      return 'linux'
    return None

class BenchmarkHealthData(ndb.Model):
  """Stores health data for a single benchmark."""
  name = ndb.StringProperty()
  owner = ndb.StringProperty()
  alerts = ndb.StructuredProperty(AlertHealthData, repeated=True)
  bots = ndb.StructuredProperty(BotHealthData, repeated=True)
  bisects = ndb.StructuredProperty(BisectHealthData, repeated=True)
  bugs = ndb.StructuredProperty(BugHealthData, repeated=True)
  reviews = ndb.StructuredProperty(ReviewData, repeated=True)
  is_complete = ndb.BooleanProperty(default=False)
  @ndb.ComputedProperty
  def no_data_on_dashboard(self):  # pylint: disable=invalid-name
    return len(self.bots) == 0
