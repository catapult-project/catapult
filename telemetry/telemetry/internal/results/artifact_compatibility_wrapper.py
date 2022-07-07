# Copyright 2019 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

# Compatibility layer for using different artifact implementations through a
# single API.
# TODO(https://crbug.com/1023458): Remove this once artifact implementations are
# unified.

from __future__ import absolute_import
import logging
import os
import six

from telemetry.internal.results import story_run

from typ import artifacts


def ArtifactCompatibilityWrapperFactory(artifact_impl):
  if isinstance(artifact_impl, story_run.StoryRun):
    return TelemetryArtifactCompatibilityWrapper(artifact_impl)
  if isinstance(artifact_impl, artifacts.Artifacts):
    return TypArtifactCompatibilityWrapper(artifact_impl)
  if isinstance(artifact_impl, FullLoggingArtifactImpl):
    return FullLoggingArtifactCompatibilityWrapper()
  if artifact_impl is None:
    return LoggingArtifactCompatibilityWrapper()
  raise RuntimeError('Given unsupported artifact implementation %s' %
                     type(artifact_impl).__name__)


class ArtifactCompatibilityWrapper():
  def __init__(self, artifact_impl):
    self._artifact_impl = artifact_impl

  def CreateArtifact(self, name, data):
    """Create an artifact with the given data.

    Args:
      name: The name of the artifact, can include '/' to organize artifacts
          within a hierarchy.
      data: The data to write to the artifact.
    """
    raise NotImplementedError()


class TelemetryArtifactCompatibilityWrapper(ArtifactCompatibilityWrapper):
  """Wrapper around Telemetry's story_run.StoryRun class."""
  def CreateArtifact(self, name, data):
    if six.PY2 or isinstance(data, bytes):
      mode = 'w+b'
    else:
      mode = 'w+'
    with self._artifact_impl.CreateArtifact(name, mode=mode) as f:
      f.write(data)


class TypArtifactCompatibilityWrapper(ArtifactCompatibilityWrapper):
  """Wrapper around typ's Artifacts class"""
  def CreateArtifact(self, name, data):
    file_relative_path = name.replace('/', os.sep)
    as_text = False
    if isinstance(data, six.string_types):
      as_text = True
    self._artifact_impl.CreateArtifact(
        name, file_relative_path, data, write_as_text=as_text)


class LoggingArtifactCompatibilityWrapper(ArtifactCompatibilityWrapper):
  """Wrapper that logs instead of actually creating artifacts.

  This is necessary because some tests, e.g. those that inherit from
  browser_test_case.BrowserTestCase, don't currently have a way of reporting
  artifacts. In those cases, we can fall back to logging to stdout so that
  information isn't lost. However, to prevent cluttering up stdout, we only log
  the first 100 characters.
  """
  def __init__(self):
    super().__init__(None)

  def CreateArtifact(self, name, data):
    # Don't log binary files as the utf-8 encoding will cause errors.
    # Note that some tests use the .dmp extension for both crash-dump files and
    # text files.
    if os.path.splitext(name)[1].lower() in ['.png', '.dmp']:
      return
    logging.warning(
        'Only logging the first 100 characters of the %d character artifact '
        'with name %s. To store the full artifact, run the test in either a '
        'Telemetry or typ context.' % (len(data), name))
    logging.info('Artifact with name %s: %s', name, data[:min(100, len(data))])


class FullLoggingArtifactImpl():
  """A dummy 'artifact implementation'.

  Used to specify that FullLoggingArtifactCompatibilityWrapper should be used
  since there is no actual backing artifact implementation.
  """


class FullLoggingArtifactCompatibilityWrapper(ArtifactCompatibilityWrapper):
  """Wrapper that logs instead of actually creating artifacts.

  Unlike LoggingArtifactCompatibilityWrapper, logs the entire artifact. This
  results in more log spam, hence why it is not the default.
  """
  def __init__(self):
    super().__init__(None)

  def CreateArtifact(self, name, data):
    # Don't log binary files as the utf-8 encoding will cause errors.
    # Note that some tests use the .dmp extension for both crash-dump files and
    # text files.
    if os.path.splitext(name)[1].lower() in ['.png', '.dmp']:
      return
    logging.info('Artifact with name %s: %s', name, data)
