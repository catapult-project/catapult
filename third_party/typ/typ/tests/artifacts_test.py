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

import os
import shutil
import tempfile
import unittest

from typ import artifacts


class ArtifactsArtifactCreationTests(unittest.TestCase):
  def _VerifyPathAndContents(self, dirname, test_name, test_basename, iteration,
      artifact_name, contents):
    path = os.path.join(
        dirname, 'iteration_%s' % iteration, test_basename, '%s-%s' % (
            test_name, artifact_name))
    self.assertTrue(os.path.exists(path))
    with open(path, 'r') as f:
      self.assertEqual(f.read(), contents)

  def test_create_artifact_writes_to_disk(self):
    """Tests CreateArtifact will write to disk at the correct location."""
    tempdir = tempfile.mkdtemp()
    try:
      ar = artifacts.Artifacts(tempdir, 'test_name', 'test_basename', 0)
      with ar.CreateArtifact('artifact_name') as f:
        f.write(b'contents')

      self._VerifyPathAndContents(tempdir, 'test_name', 'test_basename', '0',
          'artifact_name', 'contents')
    finally:
      shutil.rmtree(tempdir)

  def test_create_artifact_no_output_dir(self):
    """Tests that CreateArtifact will fail if used without an output dir."""
    art = artifacts.Artifacts(None, 'test_name', 'test_basename', 0)
    with self.assertRaises(ValueError):
      with art.CreateArtifact('artifact_name') as f:
        pass

  def test_create_artifact_duplicate(self):
    """Tests that CreateArtifact with duplicate names fails."""
    tempdir = tempfile.mkdtemp()
    try:
      ar = artifacts.Artifacts(tempdir, 'test_name', 'test_basename', 0)
      with ar.CreateArtifact('artifact_name') as f:
        f.write(b'contents')
      with self.assertRaises(ValueError):
        with ar.CreateArtifact('artifact_name') as f:
          pass
    finally:
      shutil.rmtree(tempdir)

  def test_duplicates_allowed_across_iterations(self):
    """Tests that using Artifacts with different iterations works."""
    tempdir = tempfile.mkdtemp()
    try:
      ar = artifacts.Artifacts(tempdir, 'test_name', 'test_basename', 0)
      with ar.CreateArtifact('artifact_name') as f:
        f.write(b'contents')

      another_ar = artifacts.Artifacts(tempdir, 'test_name', 'test_basename', 1)
      with another_ar.CreateArtifact('artifact_name') as f:
        f.write(b'other contents')

      self._VerifyPathAndContents(tempdir, 'test_name', 'test_basename', '0',
          'artifact_name', 'contents')
      self._VerifyPathAndContents(tempdir, 'test_name', 'test_basename', '1',
          'artifact_name', 'other contents')
    finally:
      shutil.rmtree(tempdir)


class ArtifactsLinkCreationTests(unittest.TestCase):
  def test_create_link(self):
    ar = artifacts.Artifacts(None, 'test_name', 'test_basename', 0)
    ar.CreateLink('link', 'https://testsite.com')
    self.assertEqual(ar.files, {'link': 'https://testsite.com'})

  def test_create_link_duplicate(self):
    ar = artifacts.Artifacts(None, 'test_name', 'test_basename', 0)
    ar.CreateLink('link', 'https://testsite.com')
    with self.assertRaises(ValueError):
      ar.CreateLink('link', 'https://testsite.com')

  def test_create_link_invalid_url(self):
    ar = artifacts.Artifacts(None, 'test_name', 'test_basename', 0)
    with self.assertRaises(ValueError):
      ar.CreateLink('link', 'https:/malformedurl.com')

  def test_create_link_non_https(self):
    ar = artifacts.Artifacts(None, 'test_name', 'test_basename', 0)
    with self.assertRaises(ValueError):
      ar.CreateLink('link', 'http://testsite.com')

  def test_create_link_newlines(self):
    ar = artifacts.Artifacts(None, 'test_name', 'test_basename', 0)
    with self.assertRaises(ValueError):
      ar.CreateLink('link', 'https://some\nbadurl.com')
