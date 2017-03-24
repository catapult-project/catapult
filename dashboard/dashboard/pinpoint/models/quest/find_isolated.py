# Copyright 2016 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

from dashboard.pinpoint.models import isolated
from dashboard.pinpoint.models.quest import execution
from dashboard.pinpoint.models.quest import quest


class FindIsolated(quest.Quest):

  def __init__(self, configuration):
    self._builder_name = _BuilderNameForConfiguration(configuration)

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
    isolated_hash = _LookUpIsolated(self._builder_name, self._change)
    if isolated_hash:
      self._Complete(result_arguments={'isolated_hash': isolated_hash})
      return

    # TODO: Request a fresh build using Buildbucket.
    raise NotImplementedError('Building commits outside of the Perf '
                              'waterfall is not implemented yet.')


def _LookUpIsolated(builder_name, change):
  # The continuous builders build most commits, so find out if the .isolated we
  # want has already been built and cached.

  # The continuous builders build commits as they land. If the commit is a DEPS
  # roll, the builder may break up the roll into its component commits and build
  # each one individually. It does not descend into rolls recurisvely. So we'll
  # only find the Change if it has no patches and at most one dep.

  if len(change.deps) > 1:
    return None

  if change.patch:
    return None

  git_hash = change.most_specific_commit.git_hash
  target = 'telemetry_perf_tests'  # TODO: Support other isolated targets.

  try:
    return isolated.Get(builder_name, git_hash, target)
  except KeyError:
    return None


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
