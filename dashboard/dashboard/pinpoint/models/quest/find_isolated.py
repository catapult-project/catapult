# Copyright 2016 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

from dashboard.pinpoint.models import isolated
from dashboard.pinpoint.models.quest import execution
from dashboard.pinpoint.models.quest import quest


class FindIsolated(quest.Quest):

  def __init__(self, configuration):
    self._builder_name = _BuilderNameForConfiguration(configuration)

  def __str__(self):
    return 'Build on ' + self._builder_name

  @property
  def retry_count(self):
    return 1

  def Start(self, change):
    return _FindIsolatedExecution(self._builder_name, change)


class _FindIsolatedExecution(execution.Execution):

  def __init__(self, builder_name, change):
    super(_FindIsolatedExecution, self).__init__()
    self._builder_name = builder_name
    self._change = change

  def _Poll(self):
    # Look for the .isolated in our cache.
    # TODO: Support other isolated targets.
    target = 'telemetry_perf_tests'
    try:
      isolated_hash = isolated.Get(self._builder_name, self._change, target)
    except KeyError:
      isolated_hash = None

    if isolated_hash:
      self._Complete(result_arguments={'isolated_hash': isolated_hash})
      return

    # TODO: Request a fresh build using Buildbucket.
    raise NotImplementedError('Building commits outside of the Perf '
                              'waterfall is not implemented yet.')


def _BuilderNameForConfiguration(configuration):
  # TODO: This is hacky. Ideally, the dashboard gives us more structured data
  # that we can use to figure out the builder name.
  configuration = configuration.lower()

  if 'health-plan' in configuration:
    return 'arm-builder-rel'

  if 'android' in configuration:
    # Default to 64-bit, because we expect 64-bit usage to increase over time.
    devices = ('nexus5', 'nexus6', 'nexus7', 'one')
    if (any(device in configuration for device in devices) and
        'nexus5x' not in configuration):
      return 'Android Builder'
    else:
      return 'Android arm64 Builder'
  elif 'linux' in configuration:
    return 'Linux Builder'
  elif 'mac' in configuration:
    return 'Mac Builder'
  elif 'win' in configuration:
    if configuration == 'win 7 perf':
      return 'Win Builder'
    else:
      return 'Win x64 Builder'
  else:
    raise NotImplementedError('Could not figure out what OS this configuration '
                              'is for: %s' % configuration)
