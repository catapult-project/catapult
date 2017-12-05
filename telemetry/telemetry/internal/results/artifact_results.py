# Copyright 2014 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import collections
import logging
import os
import shutil

from telemetry.internal.util import file_handle


class ArtifactResults(object):
  """Stores artifacts from test runs."""
  def __init__(self, output_dir):
    """Creates an artifact results object.

    Args:
      output_dir: The output directory where artifacts should be dumped.
    """
    # Maps test name -> mapping of artifact name to list of artifacts
    self._test_artifacts = collections.defaultdict(
        lambda: collections.defaultdict(list))
    self._artifact_dir = os.path.join(os.path.realpath(output_dir), 'artifacts')

    if not os.path.exists(self.artifact_dir):
      os.makedirs(self.artifact_dir)

  def GetTestArtifacts(self, test_name):
    """Gets all artifacts for a test.

    Returns a dict mapping artifact name to a list of relative filepaths.
    """
    return self._test_artifacts[test_name]

  @property
  def artifact_dir(self):
    return self._artifact_dir

  def AddArtifact(self, test_name, name, artifact_path, run_number=None):
    """Adds an artifact.

    Args:
      * test_name: The test which produced the artifact.
      * name: The name of the artifact.
      * artifact_path: The path to the artifact on disk. If it is not in the
          proper artifact directory, it will be moved there.
      * run_number: Which run of a test this is. If the current number of
          artifacts for the (test_name, name) key is less than this number,
          new `None` artifacts will be inserted, with the assumption that
          other runs of this test did not produce the same set of artifacts.
          NOT CURRENTLY IMPLEMENTED.
    """
    del run_number
    if isinstance(artifact_path, file_handle.FileHandle):
      artifact_path = artifact_path.GetAbsPath()

    artifact_path = os.path.realpath(artifact_path)

    # If the artifact isn't in the artifact directory, move it.
    if not artifact_path.startswith(self.artifact_dir + os.sep):
      logging.warning("Moving artifact file %r to %r" % (
          artifact_path, self.artifact_dir))
      shutil.move(artifact_path, self.artifact_dir)
      artifact_path = os.path.basename(artifact_path)
    else:
      # Make path relative to artifact directory.
      artifact_path = artifact_path[len(self.artifact_dir + os.sep):]

    # '/' is interpreted as a generic path separator. We want these paths to be
    # relative to the output directory. The filter is there because
    # os.path.split returns an empty string when run on a filename;
    # os.path.split('bar') -> ('', 'bar').
    artifact_path = '/'.join(['artifacts'] + list(
        path for path in os.path.split(artifact_path) if path))

    self._test_artifacts[test_name][name].append(artifact_path)
