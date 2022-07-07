# Copyright 2015 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

from __future__ import absolute_import
import contextlib
import datetime
import json
import logging
import numbers
import os
import posixpath
import sys
import time
import six

if sys.version_info.major == 3:
  DEFAULT_MODE = 'w+'
else:
  DEFAULT_MODE = 'w+b'


PASS = 'PASS'
FAIL = 'FAIL'
SKIP = 'SKIP'

MEASUREMENTS_NAME = 'measurements.json'

_CONTENT_TYPES = {
    '.dat': 'application/octet-stream',  # Generic data blob.
    '.dmp': 'application/x-dmp',  # A minidump file.
    '.gz': 'application/gzip',
    '.html': 'text/html',
    '.json': 'application/json',
    '.pb': 'application/x-protobuf',
    '.png': 'image/png',
    '.txt': 'text/plain',
}
_DEFAULT_CONTENT_TYPE = _CONTENT_TYPES['.dat']


def _FormatDuration(seconds):
  return '{:.2f}s'.format(seconds)


def ContentTypeFromExt(name):
  """Infer a suitable content_type from the extension in a file name."""
  _, ext = posixpath.splitext(name)
  if ext in _CONTENT_TYPES:
    return _CONTENT_TYPES[ext]
  logging.info('Unable to infer content type for artifact: %s', name)
  logging.info('Falling back to: %s', _DEFAULT_CONTENT_TYPE)
  return _DEFAULT_CONTENT_TYPE


class _Artifact():
  def __init__(self, local_path, content_type):
    """
    Args:
      local_path: an absolute local path to an artifact file.
      content_type: A string representing the MIME type of a file.
    """
    self._local_path = local_path
    self._content_type = content_type

  @property
  def local_path(self):
    return self._local_path

  @property
  def content_type(self):
    return self._content_type

  def AsDict(self):
    return {
        'filePath': self.local_path,
        'contentType': self.content_type
    }


class StoryRun():
  def __init__(self, story, test_prefix=None, index=0, intermediate_dir=None):
    """StoryRun objects track results for a single run of a story.

    Args:
      story: The story.Story being currently run.
      test_prefix: A string prefix to use for the test path identifying the
        test being run.
      index: If the same story is run multiple times, the index of this run.
      output_dir: The path to a directory where outputs are stored. Test
        artifacts, in particluar, are stored at '{output_dir}/artifacts'.
    """
    self._story = story
    self._test_prefix = test_prefix
    self._index = index
    self._tags = []
    self._skip_reason = None
    self._skip_expected = False
    self._failed = False
    self._failure_str = None
    self._start_time = time.time()
    self._end_time = None
    self._artifacts = {}
    self._measurements = {}
    self._InitTags()

    if intermediate_dir is None:
      self._artifacts_dir = None
    else:
      intermediate_dir = os.path.realpath(intermediate_dir)
      run_dir = '%s_%s' % (self._story.file_safe_name, self._index + 1)
      self._artifacts_dir = os.path.join(intermediate_dir, run_dir)
      if not os.path.exists(self._artifacts_dir):
        os.makedirs(self._artifacts_dir)

  def AddMeasurement(self, name, unit, samples, description=None):
    """Record an add hoc measurement associated with this story run."""
    assert self._measurements is not None, (
        'Measurements have already been collected')
    if not isinstance(name, six.string_types):
      raise TypeError('name must be a string, got %s' % name)
    assert name not in self._measurements, (
        'Already have measurement with the name %s' % name)
    self._measurements[name] = _MeasurementToDict(unit, samples, description)

  def _WriteMeasurementsArtifact(self):
    if self._measurements:
      with self.CreateArtifact(MEASUREMENTS_NAME) as f:
        json.dump({'measurements': self._measurements}, f)
    # It's an error to record more measurements after this point.
    self._measurements = None

  def AddTags(self, key, values):
    """Record values to be associated with a given tag key."""
    self._tags.extend({'key': key, 'value': value} for value in values)

  def _InitTags(self):
    if 'GTEST_SHARD_INDEX' in os.environ:
      self.AddTags('shard', [os.environ['GTEST_SHARD_INDEX']])
    self.AddTags('story_tag', self.story.GetStoryTagsList())

  def AddTbmMetrics(self, metrics):
    """Register Timeline Based Metrics to compute on traces for this story.

    Args:
      metrics: A list of strings, each should be of the form 'v2:metric' or
        'v3:metric' for respective TBM versioned metrics. If the version number
        is omitted, a default of 'v2' is assumed.
    """
    for metric in metrics:
      version, name = _ParseTbmMetric(metric)
      self.AddTags(version, [name])

  def SetFailed(self, failure_str):
    if self._failed:
      self._failure_str += '\n' + failure_str
    else:
      self._failed = True
      self._failure_str = failure_str

  def Skip(self, reason, expected=True):
    if not reason:
      raise ValueError('A skip reason must be given')
    # TODO(#4254): Turn this into a hard failure.
    if self.skipped:
      logging.warning(
          'Story was already skipped with reason: %s', self.skip_reason)
    self._skip_reason = reason
    self._skip_expected = expected

  def Finish(self):
    assert not self.finished, 'story run had already finished'
    self._end_time = time.time()
    self._WriteMeasurementsArtifact()

  def AsDict(self):
    """Encode as TestResultEntry dict in LUCI Test Results format.

    See: go/luci-test-results-design
    """
    assert self.finished, 'story must be finished first'
    return {
        'testResult': {
            'testPath': self.test_path,
            'resultId': str(self.index),
            'status': self.status,
            'expected': self.expected,
            'startTime': self.start_datetime.isoformat() + 'Z',
            'runDuration': _FormatDuration(self.duration),
            'outputArtifacts': {
                name: artifact.AsDict()
                for name, artifact in self._artifacts.items()
            },
            'tags': self._tags
        }
    }

  @property
  def story(self):
    return self._story

  @property
  def index(self):
    return self._index

  @property
  def test_path(self):
    if self._test_prefix is not None:
      return '/'.join([self._test_prefix, self.story.name])
    return self.story.name

  @property
  def status(self):
    if self.failed:
      return FAIL
    if self.skipped:
      return SKIP
    return PASS

  @property
  def ok(self):
    return not self.skipped and not self.failed

  @property
  def skipped(self):
    """Whether the current run is being skipped."""
    return self._skip_reason is not None

  @property
  def skip_reason(self):
    return self._skip_reason

  @property
  def expected(self):
    """Whether the test status is expected."""
    return self._skip_expected or self.ok

  # TODO(#4254): Make skipped and failed mutually exclusive and simplify these.
  @property
  def failed(self):
    return not self.skipped and self._failed

  @property
  def failure_str(self):
    return self._failure_str

  @property
  def start_datetime(self):
    return datetime.datetime.utcfromtimestamp(self._start_time)

  @property
  def start_us(self):
    return self._start_time * 1e6

  @property
  def duration(self):
    return self._end_time - self._start_time

  @property
  def finished(self):
    return self._end_time is not None

  def _PrepareLocalPath(self, name):
    """Ensure that the artifact with the given name can be created.

    Returns: absolute path to the artifact (file may not exist yet).
    """
    local_path = os.path.join(self._artifacts_dir, *name.split('/'))
    if not os.path.exists(os.path.dirname(local_path)):
      os.makedirs(os.path.dirname(local_path))
    return local_path

  @contextlib.contextmanager
  def CreateArtifact(self, name, content_type=None, mode=DEFAULT_MODE):
    """Create an artifact.

    Args:
      name: File path that this artifact will have inside the artifacts dir.
          The name can contain sub-directories with '/' as a separator.
      content_type: A string representing the MIME type of the artifact.
          If omitted a content type is inferred from a file extension in name.

    Returns:
      A generator yielding a file object.
    """
    # This is necessary for some tests.
    # TODO(crbug.com/979194): Make _artifact_dir mandatory.
    if self._artifacts_dir is None:
      yield open(os.devnull, 'w')
      return

    assert name not in self._artifacts, (
        'Story already has an artifact: %s' % name)

    local_path = self._PrepareLocalPath(name)
    if content_type is None:
      content_type = ContentTypeFromExt(name)

    with open(local_path, mode) as file_obj:
      # We want to keep track of all artifacts (e.g. logs) even in the case
      # of an exception in the client code, so we create a record for
      # this artifact before yielding the file handle.
      self._artifacts[name] = _Artifact(local_path, content_type)
      yield file_obj

  @contextlib.contextmanager
  def CaptureArtifact(self, name, content_type=None):
    """Generate an absolute file path for an artifact, but do not
    create a file. File creation is a responsibility of the caller of this
    method. It is assumed that the file exists at the exit of the context.

    Args:
      name: File path that this artifact will have inside the artifacts dir.
        The name can contain sub-directories with '/' as a separator.
      content_type: A string representing the MIME type of the artifact.
          If omitted a content type is inferred from a file extension in name.

    Returns:
      A generator yielding a file name.
    """
    assert self._artifacts_dir is not None
    assert name not in self._artifacts, (
        'Story already has an artifact: %s' % name)

    local_path = self._PrepareLocalPath(name)
    if content_type is None:
      content_type = ContentTypeFromExt(name)

    yield local_path
    assert os.path.isfile(local_path), (
        'Failed to capture an artifact: %s' % local_path)
    self._artifacts[name] = _Artifact(local_path, content_type)

  def IterArtifacts(self, subdir=None):
    """Iterate over all artifacts in a given sub-directory.

    Returns an iterator over artifacts.
    """
    for name, artifact in six.iteritems(self._artifacts):
      if subdir is None or name.startswith(posixpath.join(subdir, '')):
        yield artifact

  def HasArtifactsInDir(self, subdir):
    """Returns true if there are artifacts inside given subdirectory.
    """
    return next(self.IterArtifacts(subdir), None) is not None

  def GetArtifact(self, name):
    """Get artifact by name.

    Returns an Artifact object or None, if there's no artifact with this name.
    """
    return self._artifacts.get(name)


def _MeasurementToDict(unit, samples, description):
  """Validate a measurement and encode as a JSON serializable dict."""
  if not isinstance(unit, six.string_types):
    # TODO(crbug.com/999484): Also validate that this is a known unit.
    raise TypeError('unit must be a string, got %s' % unit)
  if not isinstance(samples, list):
    samples = [samples]
  if not all(isinstance(v, numbers.Number) for v in samples):
    raise TypeError(
        'samples must be a list of numeric values, got %s' % samples)
  measurement = {'unit': unit, 'samples': samples}
  if description is not None:
    if not isinstance(description, six.string_types):
      raise TypeError('description must be a string, got %s' % description)
    measurement['description'] = description
  return measurement


def _ParseTbmMetric(metric):
  if ':' in metric:
    version, name = metric.split(':')
    if version not in ('tbmv2', 'tbmv3'):
      raise ValueError('Invalid metric name: %s' % metric)
    return (version, name)
  return ('tbmv2', metric)
