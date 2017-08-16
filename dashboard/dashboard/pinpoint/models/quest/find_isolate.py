# Copyright 2016 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

from dashboard.pinpoint.models import isolate
from dashboard.pinpoint.models.quest import execution
from dashboard.pinpoint.models.quest import quest
from dashboard.services import buildbucket_service


BUCKET = 'master.tryserver.chromium.perf'


class BuildError(Exception):
  """Raised when the build fails."""


class FindIsolate(quest.Quest):

  def __init__(self, configuration):
    self._builder_name = _BuilderNameForConfiguration(configuration)

  def __eq__(self, other):
    return (isinstance(other, type(self)) and
            self._builder_name == other._builder_name)

  def __str__(self):
    return 'Build on ' + self._builder_name

  @property
  def retry_count(self):
    return 1

  def Start(self, change):
    return _FindIsolateExecution(self._builder_name, change)


class _FindIsolateExecution(execution.Execution):

  def __init__(self, builder_name, change):
    super(_FindIsolateExecution, self).__init__()
    self._builder_name = builder_name
    self._change = change
    self._build = None

  def _Poll(self):
    # Look for the .isolate in our cache.
    # TODO: Support other isolate targets.
    target = 'telemetry_perf_tests'
    try:
      isolate_hash = isolate.Get(self._builder_name, self._change, target)
    except KeyError:
      isolate_hash = None

    if isolate_hash:
      self._Complete(result_arguments={'isolate_hash': isolate_hash})
      return

    # Check the status of a previously requested build.
    if self._build:
      status = buildbucket_service.GetJobStatus(self._build)

      if status['build']['status'] != 'COMPLETED':
        return

      if status['build']['result'] == 'FAILURE':
        raise BuildError('Build failed: ' + status['build']['failure_reason'])
      elif status['build']['result'] == 'CANCELED':
        raise BuildError('Build was canceled: ' +
                         status['build']['cancelation_reason'])
      else:
        # It's possible for there to be a race condition if the builder uploads
        # the isolate and completes the build between the above isolate lookup
        # and buildbucket lookup, but right now, it takes builds a few minutes
        # to package the build, so that doesn't happen.
        raise BuildError('Buildbucket says the build completed successfully, '
                         "but Pinpoint can't find the isolate hash.")

    # Request a build!
    self._build = _RequestBuild(self._builder_name, self._change)['build']['id']


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


def _RequestBuild(builder_name, change):
  deps_overrides = {dep.repository_url: dep.git_hash for dep in change.deps}
  parameters = {
      'builder_name': builder_name,
      'properties': {
          'clobber': True,
          'parent_got_revision': change.base_commit.git_hash,
          'deps_revision_overrides': deps_overrides,
      },
  }

  if change.patch:
    # TODO: Support Gerrit.
    # https://github.com/catapult-project/catapult/issues/3599
    parameters['properties'].update({
        'patch_storage': 'rietveld',
        'rietveld': change.patch.server,
        'issue': change.patch.issue,
        'patchset': change.patch.patchset,
    })

  # TODO: Look up Buildbucket bucket from builder_name.
  return buildbucket_service.Put(BUCKET, parameters)
