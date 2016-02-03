# Copyright 2015 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

"""The datastore models for graph data.

The Chromium project uses Buildbot to run its performance tests, and the
structure of the data for the Performance Dashboard reflects this. Metadata
about tests are structured in a hierarchy of Master, Bot, and Test entities.
Master and Bot entities represent Buildbot masters and builders respectively,
and Test entities represent groups of results, or individual data series.

For example, entities might be structured as follows:

  Master: ChromiumPerf
    Bot: win7
      Test: page_cycler.moz
        Test: times
          Test: page_load_time
          Test: page_load_time_ref
          Test: www.amazon.com
          Test: www.bing.com
        Test: commit_charge
          Test: ref
          Test: www.amazon.com
          Test: www.bing.com

The graph data points are represented by Row entities. Each Row entity contains
a revision and value, which are its X and Y values on a graph, and any other
metadata associated with an individual performance test result.

The keys of the Row entities for a particular data series are start with a
TestContainer key, instead of a Test key. This way, the Row entities for each
data series are in a different "entity group". This allows a faster rate of
putting data in the datastore for many series at once.

For example, Row entities are organized like this:

  TestContainer: ChromiumPerf/win7/page_cycler.moz/times/page_load_time
    Row: revision 12345, value 2.5
    Row: revision 12346, value 2.0
    Row: revision 12347, value 2.1
  TestContainer: ChromiumPerf/win7/page_cycler.moz/times/page_load_time_ref
    Row: revision 12345, value 2.4
    Row: revision 12346, value 2.0
    Row: revision 12347, value 2.2
  TestContainer: ChromiumPerf/win7/page_cycler.moz/commit_charge
    Row: revision 12345, value 10
    Row: revision 12346, value 12
    Row: revision 12347, value 11


IMPORTANT: If you add new kinds to this file, you must also add them to the
Daily Backup url in cron.yaml in order for them to be properly backed up.
See: https://developers.google.com/appengine/articles/scheduled_backups
"""

import logging

from google.appengine.ext import ndb

from dashboard import layered_cache
from dashboard import utils
from dashboard.models import anomaly
from dashboard.models import anomaly_config
from dashboard.models import internal_only_model
from dashboard.models import sheriff as sheriff_module
from dashboard.models import stoppage_alert as stoppage_alert_module

# Maximum level of nested tests.
MAX_TEST_ANCESTORS = 10

# Keys to the datastore-based cache. See stored_object.
LIST_TESTS_SUBTEST_CACHE_KEY = 'list_tests_get_tests_new_%s_%s_%s'

_MAX_STRING_LENGTH = 500


class Master(internal_only_model.InternalOnlyModel):
  """Information about the Buildbot master.

  Masters are keyed by name, e.g. 'ChromiumGPU' or 'ChromiumPerf'.
  All Bot entities that are Buildbot slaves of one master are children of one
  Master entity in the datastore.
  """
  # Master has no properties; the name of the master is the ID.


class Bot(internal_only_model.InternalOnlyModel):
  """Information about a Buildbot slave that runs perf tests.

  Bots are keyed by name, e.g. 'xp-release-dual-core'. A Bot entity contains
  information about whether the tests are only viewable to internal users, and
  each bot has a parent that is a Master entity. A Bot is be the ancestor of
  the Test entities that run on it.
  """
  internal_only = ndb.BooleanProperty(default=False, indexed=True)


class Test(internal_only_model.CreateHookInternalOnlyModel):
  """A Test entity is a node in a hierarchy of tests.

  A Test entity can represent a specific series of results which will be
  plotted on a graph, or it can represent a group of such series of results, or
  both. A Test entity that the property has_rows set to True corresponds to a
  trace on a graph, and the parent Test for a group of such tests corresponds to
  a graph with several traces. A parent Test for that test would correspond to a
  group of related graphs. Top-level Tests (also known as test suites) are
  parented by a Bot.

  Tests are keyed by name, and they also contain other metadata such as
  description and units.

  NOTE: If you remove any properties from Test, they should be added to the
  TEST_EXCLUDE_PROPERTIES list in migrate_test_names.py.
  """
  internal_only = ndb.BooleanProperty(default=False, indexed=True)

  # Sheriff rotation for this test. Rotations are specified by regular
  # expressions that can be edited at /edit_sheriffs.
  sheriff = ndb.KeyProperty(kind=sheriff_module.Sheriff, indexed=True)

  # There is a default anomaly threshold config (in anomaly.py), and it can
  # be overridden for a group of tests by using /edit_sheriffs.
  overridden_anomaly_config = ndb.KeyProperty(
      kind=anomaly_config.AnomalyConfig, indexed=True)

  # Keep track of what direction is an improvement for this graph so we can
  # filter out alerts on regressions.
  improvement_direction = ndb.IntegerProperty(
      default=anomaly.UNKNOWN,
      choices=[
          anomaly.UP,
          anomaly.DOWN,
          anomaly.UNKNOWN
      ],
      indexed=False
  )

  # Units of the child Rows of this Test, or None if there are no child Rows.
  units = ndb.StringProperty(indexed=False)

  # The last alerted revision is used to avoid duplicate alerts.
  last_alerted_revision = ndb.IntegerProperty(indexed=False)

  # Whether or not the test has child rows. Set by hook on Row class put.
  has_rows = ndb.BooleanProperty(default=False, indexed=True)

  # If there is a currently a StoppageAlert that indicates that data hasn't
  # been received for some time, then will be set. Otherwise, it is None.
  stoppage_alert = ndb.KeyProperty(
      kind=stoppage_alert_module.StoppageAlert, indexed=True)

  # A test is marked "deprecated" if no new points have been received for
  # a long time; these tests should usually not be listed.
  deprecated = ndb.BooleanProperty(default=False, indexed=True)

  # For top-level test entities, this is a list of sub-tests that are checked
  # for alerts (i.e. they have a sheriff). For other tests, this is empty.
  monitored = ndb.KeyProperty(repeated=True, indexed=True)

  # Description of what the test measures.
  description = ndb.TextProperty(indexed=True)

  # Source code location of the test. Optional.
  code = ndb.StringProperty(indexed=False, repeated=True)

  # Command to run the test. Optional.
  command_line = ndb.StringProperty(indexed=False)

  # Computed properties are treated like member variables, so they have
  # lowercase names, even though they look like methods to pylint.
  # pylint: disable=invalid-name

  @ndb.ComputedProperty
  def bot(self):  # pylint: disable=invalid-name
    """Immediate parent Bot entity, or None if this is not a test suite."""
    parent = self.key.parent()
    if parent.kind() == 'Bot':
      return parent
    return None

  @ndb.ComputedProperty
  def parent_test(self):  # pylint: disable=invalid-name
    """Immediate parent Test entity, or None if this is a test suite."""
    parent = self.key.parent()
    if parent.kind() == 'Test':
      return parent
    return None

  @property
  def test_path(self):
    """Slash-separated list of key parts, 'master/bot/suite/chart/...'."""
    return utils.TestPath(self.key)

  @ndb.ComputedProperty
  def master_name(self):
    return self.key.pairs()[0][1]

  @ndb.ComputedProperty
  def bot_name(self):
    return self.key.pairs()[1][1]

  @ndb.ComputedProperty
  def suite_name(self):
    return self.key.pairs()[2][1]

  @ndb.ComputedProperty
  def test_part1_name(self):
    pairs = self.key.pairs()
    if len(pairs) < 4:
      return ''
    return self.key.pairs()[3][1]

  @ndb.ComputedProperty
  def test_part2_name(self):
    pairs = self.key.pairs()
    if len(pairs) < 5:
      return ''
    return self.key.pairs()[4][1]

  @ndb.ComputedProperty
  def test_part3_name(self):
    pairs = self.key.pairs()
    if len(pairs) < 6:
      return ''
    return self.key.pairs()[5][1]

  @ndb.ComputedProperty
  def test_part4_name(self):
    pairs = self.key.pairs()
    if len(pairs) < 7:
      return ''
    return self.key.pairs()[6][0]

  @classmethod
  def _GetMasterBotSuite(cls, key):
    while key and key.parent():
      if key.parent().kind() == 'Bot':
        if not key.parent().parent():
          return None
        return (key.parent().parent().string_id(),
                key.parent().string_id(),
                key.string_id())
      key = key.parent()
    return None

  def __init__(self, *args, **kwargs):
    # Indexed StringProperty has a maximum length. If this length is exceeded,
    # then an error will be thrown in ndb.Model.__init__.
    # Truncate the "description" property if necessary.
    description = kwargs.get('description') or ''
    kwargs['description'] = description[:_MAX_STRING_LENGTH]
    super(Test, self).__init__(*args, **kwargs)

  def _pre_put_hook(self):
    """This method is called before a Test is put into the datastore.

    Here, we check the sheriffs and anomaly configs to make sure they are
    current. We also update the monitored list of the test suite.
    """
    # Set the sheriff to the first sheriff (alphabetically by sheriff name)
    # that has a test pattern that matches this test.
    self.sheriff = None
    for sheriff_entity in sheriff_module.Sheriff.query().fetch():
      for pattern in sheriff_entity.patterns:
        if utils.TestMatchesPattern(self, pattern):
          self.sheriff = sheriff_entity.key
      if self.sheriff:
        break

    # If this Test is monitored, add it to the monitored list of its test suite.
    # A test is be monitored iff it has a sheriff, and monitored tests are
    # tracked in the monitored list of a test suite Test entity.
    test_suite = ndb.Key(*self.key.flat()[:6]).get()
    if self.sheriff:
      if test_suite and self.key not in test_suite.monitored:
        test_suite.monitored.append(self.key)
        test_suite.put()
    elif test_suite and self.key in test_suite.monitored:
      test_suite.monitored.remove(self.key)
      test_suite.put()

    # Set the anomaly threshold config to the first one that has a test pattern
    # that matches this test, if there is one. Anomaly configs are sorted by
    # name, so that a config with a name that comes earlier lexicographically
    # is considered higher-priority.
    self.overridden_anomaly_config = None
    anomaly_configs = anomaly_config.AnomalyConfig.query().fetch()
    anomaly_configs.sort(key=lambda config: config.key.string_id())
    for anomaly_config_entity in anomaly_configs:
      for pattern in anomaly_config_entity.patterns:
        if utils.TestMatchesPattern(self, pattern):
          self.overridden_anomaly_config = anomaly_config_entity.key
      if self.overridden_anomaly_config:
        break

  def CreateCallback(self):
    """Called when the entity is first saved."""
    if self.key.parent().kind() != 'Bot':
      layered_cache.Delete(
          LIST_TESTS_SUBTEST_CACHE_KEY % self._GetMasterBotSuite(self.key))

  @classmethod
  # pylint: disable=unused-argument
  def _pre_delete_hook(cls, key):
    if key.parent() and key.parent().kind() != 'Bot':
      layered_cache.Delete(
          LIST_TESTS_SUBTEST_CACHE_KEY % Test._GetMasterBotSuite(key))


class LastAddedRevision(ndb.Model):
  """Represents the last added revision for a test path.

  The reason this property is separated from Test entity is to avoid contention
  issues (Frequent update of entity within the same group).  This property is
  updated very frequent in /add_point.
  """
  revision = ndb.IntegerProperty(indexed=False)


class Row(internal_only_model.InternalOnlyModel, ndb.Expando):
  """A Row represents one data point.

  A Row has a revision and a value, which are the X and Y values, respectively.
  Each Row belongs to one Test, along with all of the other Row entities that
  it is plotted with. Rows are keyed by revision.

  In addition to the properties defined below, Row entities may also have other
  properties which specify additional supplemental data. These are called
  "supplemental columns", and should have the following prefixes:
    d_: A data point, such as d_1st_run or d_50th_percentile. FloatProperty.
    r_: Revision such as r_webkit or r_v8. StringProperty, limited to 25
        characters, '0-9' and '.'.
    a_: Annotation such as a_chrome_bugid or a_gasp_anomaly. StringProperty.
  """
  # Don't index by default (only explicitly indexed properties are indexed).
  _default_indexed = False
  internal_only = ndb.BooleanProperty(default=False, indexed=True)

  # The parent_test is the key of the Test entity that this Row belongs to.
  @ndb.ComputedProperty
  def parent_test(self):  # pylint: disable=invalid-name
    # The Test entity that a Row belongs to isn't actually its parent in the
    # datastore. Rather, the parent key of each Row contains a test path, which
    # contains the information necessary to get the actual Test key.
    return utils.TestKey(self.key.parent().string_id())

  # Points in each graph are sorted by "revision". This is usually a Chromium
  # SVN version number, but it might also be any other integer, as long as
  # newer points have higher numbers.
  @ndb.ComputedProperty
  def revision(self):  # pylint: disable=invalid-name
    return self.key.integer_id()

  # The time the revision was added to the dashboard is tracked in order
  # to too many points from being added in a short period of time, which would
  # indicate an error or malicious code.
  timestamp = ndb.DateTimeProperty(auto_now_add=True, indexed=True)

  # The Y-value at this point.
  value = ndb.FloatProperty(indexed=True)

  # The standard deviation at this point. Optional.
  error = ndb.FloatProperty(indexed=False)

  def _pre_put_hook(self):
    """Sets the has_rows property of the parent test before putting this Row.

    This isn't atomic because the parent_test put() and Row put() don't happen
    in the same transaction. But in practice it shouldn't be an issue because
    the parent test will get more points as the test runs.
    """
    parent_test = self.parent_test.get()

    # If the Test pointed to by parent_test is not valid, that indicates
    # that a Test entity was not properly created in add_point.
    if not parent_test:
      parent_key = self.key.parent()
      logging.warning('Row put without valid Test. Parent key: %s', parent_key)
      return

    if not parent_test.has_rows:
      parent_test.has_rows = True
      parent_test.put()
