# Copyright 2015 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import contextlib
import datetime
import logging
import os
import shutil
import tempfile
import time
import uuid

from py_utils import cloud_storage  # pylint: disable=import-error

from telemetry.internal.util import file_handle


PASS = 'PASS'
FAIL = 'FAIL'
SKIP = 'SKIP'


def _FormatTimeStamp(epoch):
  return datetime.datetime.utcfromtimestamp(epoch).isoformat() + 'Z'


def _FormatDuration(seconds):
  return '{:.2f}s'.format(seconds)


class StoryRun(object):
  def __init__(self, story, output_dir=None):
    self._story = story
    self._values = []
    self._tbm_metrics = []
    self._skip_reason = None
    self._skip_expected = False
    self._failed = False
    self._failure_str = None
    self._start_time = time.time()
    self._end_time = None
    self._artifacts = {}
    self._output_dir = output_dir

    if self._output_dir is None:
      self._artifact_dir = None
    else:
      self._artifact_dir = os.path.join(self._output_dir, 'artifacts')
      if not os.path.exists(self._artifact_dir):
        os.makedirs(self._artifact_dir)


  def AddValue(self, value):
    self._values.append(value)

  def SetTbmMetrics(self, metrics):
    assert not self._tbm_metrics, 'Metrics have already been set'
    assert len(metrics) > 0, 'Metrics should not be empty'
    self._tbm_metrics = metrics

  def SetFailed(self, failure_str):
    self._failed = True
    self._failure_str = failure_str

  def Skip(self, reason, is_expected=True):
    if not reason:
      raise ValueError('A skip reason must be given')
    # TODO(#4254): Turn this into a hard failure.
    if self.skipped:
      logging.warning(
          'Story was already skipped with reason: %s', self.skip_reason)
    self._skip_reason = reason
    self._skip_expected = is_expected

  def Finish(self):
    assert not self.finished, 'story run had already finished'
    self._end_time = time.time()

  def AsDict(self):
    """Encode as TestResultEntry dict in LUCI Test Results format.

    See: go/luci-test-results-design
    """
    assert self.finished, 'story must be finished first'
    return {
        'testResult': {
            'testName': self.test_name,
            'status': self.status,
            'isExpected': self.is_expected,
            'startTime': _FormatTimeStamp(self._start_time),
            'runDuration': _FormatDuration(self.duration)
        }
    }

  @property
  def story(self):
    return self._story

  @property
  def test_name(self):
    # TODO(crbug.com/966835): This should be prefixed with the benchmark name.
    return self.story.name

  @property
  def values(self):
    """The values that correspond to this story run."""
    return self._values

  @property
  def tbm_metrics(self):
    """The TBMv2 metrics that will computed on this story run."""
    return self._tbm_metrics

  @property
  def status(self):
    if self.failed:
      return FAIL
    elif self.skipped:
      return SKIP
    else:
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
  def is_expected(self):
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
  def duration(self):
    return self._end_time - self._start_time

  @property
  def finished(self):
    return self._end_time is not None

  @contextlib.contextmanager
  def CreateArtifact(self, name, prefix, suffix):
    """Create an artifact.

    Args:
      * name: The name of this artifact; 'logs', 'screenshot'.  Note that this
          isn't used as part of the file name.
      * prefix: A string to appear at the beginning of the file name.
      * suffix: A string to appear at the end of the file name.
    Returns:
      A generator yielding a file object.
    """
    if self._output_dir is None:  # for tests
      yield open(os.devnull, 'w')
      return

    assert name not in self._artifacts, (
        'Story already has an artifact: %s' % name)

    with tempfile.NamedTemporaryFile(
        prefix=prefix, suffix=suffix, dir=self._artifact_dir,
        delete=False) as file_obj:
      self.AddArtifact(name, file_obj.name)
      yield file_obj

  def AddArtifact(self, name, artifact_path):
    """Adds an artifact.

    Args:
      * name: The name of the artifact.
      * artifact_path: The path to the artifact on disk. If it is not in the
          proper artifact directory, it will be moved there.
    """
    if self._output_dir is None:  # for tests
      return

    assert name not in self._artifacts, (
        'Story already has an artifact: %s' % name)

    if isinstance(artifact_path, file_handle.FileHandle):
      artifact_path = artifact_path.GetAbsPath()

    artifact_path = os.path.realpath(artifact_path)

    # If the artifact isn't in the artifact directory, move it.
    if not artifact_path.startswith(self._artifact_dir + os.sep):
      logging.warning("Moving artifact file %r to %r" % (
          artifact_path, self._artifact_dir))
      shutil.move(artifact_path, self._artifact_dir)
      artifact_path = os.path.join(self._artifact_dir,
                                   os.path.basename(artifact_path))

    # Make path relative to output directory.
    artifact_path = artifact_path[len(self._output_dir + os.sep):]

    self._artifacts[name] = artifact_path


  def IterArtifacts(self):
    """Iterates over all artifacts for this test.

    Returns an iterator over (name, path) tuples.
    """
    return self._artifacts.iteritems()

  def GetArtifact(self, name):
    """Gets artifact by name.

    Returns a filepath or None, if there's no artifact with this name.
    """
    return self._artifacts.get(name)

  def UploadArtifactsToCloud(self, bucket):
    """Uploads all artifacts of the test to cloud storage.

    Local artifact paths are changed to their respective cloud URLs.
    """
    for name, local_path in self.IterArtifacts():
      abs_artifact_path = os.path.abspath(os.path.join(
          self._output_dir, local_path))
      remote_path = str(uuid.uuid1())
      cloud_url = cloud_storage.Insert(bucket, remote_path, abs_artifact_path)
      self._artifacts[name] = cloud_url
      logging.warning('Uploading %s of page %s to %s\n' % (
          name, self._story.name, cloud_url))
