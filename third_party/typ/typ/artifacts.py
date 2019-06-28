 # Copyright 2019 Google Inc. All rights reserved.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#    http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

import contextlib
import os
import sys

if sys.version_info.major == 2:
  import urlparse
else:
  import urllib.parse as urlparse


class Artifacts(object):
  def __init__(self, output_dir, test_name, test_basename, iteration):
    """Creates an artifact results object.

    This provides a way for tests to write arbitrary files to disk, either to
    be processed at a later point by a recipe or merge script, or simply as a
    way of saving additional data for users to later view.

    Artifacts are saved to disk in the following hierarchy in the output
    directory:
      * iteration
      * test basename
      * test name "-" artifact name
    For example, an artifact named "screenshot.png" for the first iteration of
    the "TestFoo.test_bar" test will have the path:
    iteration_0/TestFoo/test_bar-screenshot.png

    See https://chromium.googlesource.com/chromium/src/+/master/docs/testing/json_test_results_format.md
    for documentation on the output format for artifacts.

    The original design doc for this class can be found at
    https://docs.google.com/document/d/1gChmrnkHT8_MuSCKlGo-hGPmkEzg425E8DASX57ODB0/edit?usp=sharing,
    open to all chromium.org accounts.

    Args:
      output_dir: The directory that artifacts should be saved to on disk.
      test_name: The name of the test associated with this Artifacts
          instance.
      test_basename: The basename for the test associated with this Artifacts
          instance, i.e. all the stuff before the specific test name.
      iteration: Which iteration of the test this is. Used to distinguish
          artifacts from different runs of the same test.
    """
    self._output_dir = output_dir
    self._test_name = test_name
    self._test_basename = test_basename
    self._iteration = iteration
    # A map of artifact names to their filepaths relative to the output
    # directory.
    self.files = {}

  @contextlib.contextmanager
  def CreateArtifact(self, artifact_name):
    """Creates an artifact and yields a handle to its File object.

    Args:
      artifact_name: A string specifying the name for the artifact, such as
          "failure_screenshot.png" or "benchmark_log.txt". This should be unique
          for each artifact within a single test.
    """
    self._AssertOutputDir()
    self._AssertNoDuplicates(artifact_name)
    artifact_path = self._GenerateRelativeArtifactPath(artifact_name)

    full_artifact_path = os.path.join(self._output_dir, artifact_path)
    if not os.path.exists(os.path.dirname(full_artifact_path)):
      os.makedirs(os.path.dirname(full_artifact_path))

    self.files[artifact_name] = artifact_path
    with open(full_artifact_path, 'wb') as f:
      yield f

  def CreateLink(self, artifact_name, path):
    """Creates a special link/URL artifact.

    Instead of providing a File handle to be written to, the provided |path|
    will be directly used as the artifact's path.

    Args:
      artifact_name: A string specifying the name for the artifact, such as
          "triage_url".
      path: A string to be used for the artifact's path. Must be an HTTPS
          URL.
    """
    # Don't need to assert that we have an output dir since we aren't writing
    # any files.
    self._AssertNoDuplicates(artifact_name)
    path = path.strip()
    # Make sure that what we're given is at least vaguely URL-like.
    parse_result = urlparse.urlparse(path)
    if not parse_result.scheme or not parse_result.netloc or len(
        path.splitlines()) > 1:
      raise ValueError('Given path %s does not appear to be a URL' % path)

    if parse_result.scheme != 'https':
      raise ValueError('Only HTTPS URLs are supported.')

    self.files[artifact_name] = path

  def _GenerateRelativeArtifactPath(self, artifact_name):
    return os.path.join('iteration_%d' % self._iteration, self._test_basename,
        '%s-%s' % (self._test_name, artifact_name))

  def _AssertOutputDir(self):
    if not self._output_dir:
      raise ValueError(
          'CreateArtifact() called on an Artifacts instance without an output '
          'directory set. To fix, pass --write-full-results-to to the test.')

  def _AssertNoDuplicates(self, artifact_name):
    if artifact_name in self.files:
      raise ValueError('Artifact %s already created for test %s' % (
          artifact_name, self._test_name))
