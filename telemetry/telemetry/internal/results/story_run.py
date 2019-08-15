# Copyright 2015 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import contextlib
import datetime
import logging
import os
import posixpath
import time
import urllib


PASS = 'PASS'
FAIL = 'FAIL'
SKIP = 'SKIP'


_CONTENT_TYPES = {
    '.dat': 'application/octet-stream',  # Generic data blob.
    '.dmp': 'application/x-dmp',  # A minidump file.
    '.gz': 'application/gzip',
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
  else:
    logging.info('Unable to infer content type for artifact: %s', name)
    logging.info('Falling back to: %s', _DEFAULT_CONTENT_TYPE)
    return _DEFAULT_CONTENT_TYPE


class Artifact(object):
  def __init__(self, name, local_path, content_type):
    """
    Args:
      name: name of the artifact.
      local_path: an absolute local path to an artifact file.
      content_type: A string representing the MIME type of a file.
    """
    self._name = name
    self._local_path = local_path
    self._content_type = content_type
    self._url = None

  @property
  def name(self):
    return self._name

  @property
  def local_path(self):
    return self._local_path

  @property
  def content_type(self):
    return self._content_type

  @property
  def url(self):
    return self._url

  def SetUrl(self, url):
    assert not self._url, 'Artifact URL has been already set'
    self._url = url

  def AsDict(self):
    d = {
        'filePath': self.local_path,
        'contentType': self.content_type
    }
    # TODO(crbug.com/981349): Remove this when artifact uploading is
    # switched over to the results processor.
    if self.url:
      d['remoteUrl'] = self.url
    return d


class StoryRun(object):
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
    self._values = []
    self._tbm_metrics = []
    self._skip_reason = None
    self._skip_expected = False
    self._failed = False
    self._failure_str = None
    self._start_time = time.time()
    self._end_time = None
    self._artifacts = {}

    if intermediate_dir is None:
      self._artifacts_dir = None
    else:
      intermediate_dir = os.path.realpath(intermediate_dir)
      run_dir = '%s_%s' % (self._story.file_safe_name, self._index + 1)
      self._artifacts_dir = os.path.join(intermediate_dir, run_dir)
      if not os.path.exists(self._artifacts_dir):
        os.makedirs(self._artifacts_dir)

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
            'testPath': self.test_path,
            'status': self.status,
            'isExpected': self.is_expected,
            'startTime': self.start_datetime.isoformat() + 'Z',
            'runDuration': _FormatDuration(self.duration),
            'artifacts': {
                name: artifact.AsDict()
                for name, artifact in self._artifacts.items()}
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
    # Some stories use URLs as names, often containing special characters.
    # To avoid potential issues, and to make it easy to identify the components
    # on a test_path, we percent encode those special chars.
    # TODO(crbug.com/983993): Remove this when all stories have good names.
    story_name = urllib.quote(self.story.name, safe='')
    if self._test_prefix is not None:
      return '/'.join([self._test_prefix, story_name])
    else:
      return story_name

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
  def CreateArtifact(self, name, content_type=None):
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

    with open(local_path, 'w+b') as file_obj:
      # We want to keep track of all artifacts (e.g. logs) even in the case
      # of an exception in the client code, so we create a record for
      # this artifact before yielding the file handle.
      self._artifacts[name] = Artifact(name, local_path, content_type)
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
    self._artifacts[name] = Artifact(name, local_path, content_type)

  def IterArtifacts(self, subdir=None):
    """Iterate over all artifacts in a given sub-directory.

    Returns an iterator over artifacts.
    """
    for name, artifact in self._artifacts.iteritems():
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
