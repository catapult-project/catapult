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
  def __init__(self, output_dir, iteration=0, test_name='',
               intial_results_base_dir=False):
    """Creates an artifact results object.

    This provides a way for tests to write arbitrary files to disk, either to
    be processed at a later point by a recipe or merge script, or simply as a
    way of saving additional data for users to later view.

    Artifacts are saved to disk in the following hierarchy in the output
    directory:
      * retry_x if the test is being retried for the xth time. If x is 0
            then the files will be saved directly to the output_dir directory,
            unless the intial_results_base_dir argument is set to True. If it set
            to true then a "intial" sub directory will be created and that is
            where the artifacts will be saved.
      * test_name if the argument is specified. If it is not specified,
            then the files will be saved to the retry_x, intial or the output_dir directory.
      * relative file path
    For example,  an artifact with path "images/screenshot.png" for the first iteration of
    the "TestFoo.test_bar" test will have the path:
    TestFoo.test_bar/retry_1/images/screenshot.png

    See https://chromium.googlesource.com/chromium/src/+/master/docs/testing/json_test_results_format.md
    for documentation on the output format for artifacts.

    The original design doc for this class can be found at
    https://docs.google.com/document/d/1gChmrnkHT8_MuSCKlGo-hGPmkEzg425E8DASX57ODB0/edit?usp=sharing,
    open to all chromium.org accounts.
    """
    self._output_dir = output_dir
    self._iteration = iteration
    self._test_base_dir = test_name
    # A map of artifact names to their filepaths relative to the output
    # directory.
    self.artifacts = {}
    self._artifact_set = set()
    self._intial_results_base_dir = intial_results_base_dir

  @contextlib.contextmanager
  def CreateArtifact(self, artifact_name, file_relative_path):
    """Creates an artifact and yields a handle to its File object.

    Args:
      artifact_name: A string specifying the name for the artifact, such as
          "reftest_mismatch_actual" or "screenshot".
    """
    self._AssertOutputDir()
    if self._iteration:
        file_relative_path = os.path.join(
            'retry_%d' % self._iteration, file_relative_path)
    elif self._intial_results_base_dir:
        file_relative_path = os.path.join('initial', file_relative_path)
    dir = self._output_dir
    if self._test_base_dir:
        dir = os.path.join(dir, self._test_base_dir)
    abs_artifact_path = os.path.join(dir, file_relative_path)
    if not os.path.exists(os.path.dirname(abs_artifact_path)):
      os.makedirs(os.path.dirname(abs_artifact_path))

    if file_relative_path in self._artifact_set:
        raise ValueError('Artifact %s was already added' % (file_relative_path))
    else:
        self._artifact_set.add(file_relative_path)

    self.artifacts.setdefault(artifact_name, []).append(file_relative_path)

    if os.path.exists(abs_artifact_path):
        raise ValueError('%s already exists.' % abs_artifact_path)

    with open(abs_artifact_path, 'wb') as f:
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
    path = path.strip()
    # Make sure that what we're given is at least vaguely URL-like.
    parse_result = urlparse.urlparse(path)
    if not parse_result.scheme or not parse_result.netloc or len(
        path.splitlines()) > 1:
      raise ValueError('Given path %s does not appear to be a URL' % path)
    if parse_result.scheme != 'https':
      raise ValueError('Only HTTPS URLs are supported.')
    self.artifacts[artifact_name] = [path]

  def _AssertOutputDir(self):
    if not self._output_dir:
      raise ValueError(
          'CreateArtifact() called on an Artifacts instance without an output '
          'directory set. To fix, pass --write-full-results-to to the test.')
