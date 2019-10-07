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


class _FakeFileManager(object):
    def __init__(self, disc):
        self.disc = disc

    def open(self, path, _):
        self.path = path
        self.disc[path] = ''
        return self

    def exists(self, path):
        return  path in self.disc

    def write(self, content):
        self.disc[self.path] += content

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_value, tb):
        pass


class ArtifactsArtifactCreationTests(unittest.TestCase):

  def _VerifyPathAndContents(
      self, output_dir, file_rel_path, contents, iteration=0, test_base_dir='',
      intial_results_base_dir=False):
    path = output_dir
    if test_base_dir:
        path = os.path.join(path, test_base_dir)
    if iteration:
        path = os.path.join(path, 'retry_%d' % iteration)
    elif intial_results_base_dir:
        path = os.path.join(path, 'initial')
    path = os.path.join(path, file_rel_path)
    self.assertTrue(os.path.exists(path))
    with open(path, 'r') as f:
      self.assertEqual(f.read(), contents)

  def test_create_artifact_writes_to_disk_iteration_0_no_test_dir(self):
    """Tests CreateArtifact will write to disk at the correct location."""
    tempdir = tempfile.mkdtemp()
    try:
      ar = artifacts.Artifacts(tempdir)
      file_rel_path = os.path.join('stdout', 'text.txt')
      with ar.CreateArtifact('artifact_name', file_rel_path) as f:
        f.write(b'contents')
      self._VerifyPathAndContents(tempdir, file_rel_path, b'contents')
    finally:
      shutil.rmtree(tempdir)

  def test_create_artifact_writes_to_disk_iteration_1_no_test_dir(self):
    """Tests CreateArtifact will write to disk at the correct location."""
    tempdir = tempfile.mkdtemp()
    try:
      ar = artifacts.Artifacts(tempdir, iteration=1)
      file_rel_path = os.path.join('stdout', 'text.txt')
      with ar.CreateArtifact('artifact_name', file_rel_path) as f:
        f.write(b'contents')
      self._VerifyPathAndContents(tempdir, file_rel_path, b'contents', iteration=1)
    finally:
      shutil.rmtree(tempdir)

  def test_create_artifact_writes_to_disk_iteration_1_test_dir(self):
    """Tests CreateArtifact will write to disk at the correct location."""
    tempdir = tempfile.mkdtemp()
    try:
      ar = artifacts.Artifacts(tempdir, iteration=1, test_name='a.b.c')
      file_rel_path = os.path.join('stdout', 'text.txt')
      with ar.CreateArtifact('artifact_name', file_rel_path) as f:
        f.write(b'contents')
      self._VerifyPathAndContents(
          tempdir, file_rel_path, b'contents', iteration=1, test_base_dir='a.b.c')
    finally:
      shutil.rmtree(tempdir)

  def test_create_artifact_overwriting_artifact_raises_value_error(self):
    """Tests CreateArtifact will write to disk at the correct location."""
    tempdir = tempfile.mkdtemp()
    try:
      ar = artifacts.Artifacts(tempdir, iteration=1, test_name='a.b.c')
      file_rel_path = os.path.join('stdout', 'text.txt')
      with ar.CreateArtifact('artifact_name', file_rel_path) as f:
        f.write(b'contents')
      ar = artifacts.Artifacts(tempdir, iteration=0, test_name='a.b.c')
      file_rel_path = os.path.join('retry_1', 'stdout', 'text.txt')
      with self.assertRaises(ValueError) as ve:
          with ar.CreateArtifact('artifact_name', file_rel_path) as f:
              f.write(b'contents')
      self.assertIn('already exists.', str(ve.exception))
    finally:
      shutil.rmtree(tempdir)

  def test_create_artifact_writes_to_disk_initial_results_dir(self):
    """Tests CreateArtifact will write to disk at the correct location."""
    tempdir = tempfile.mkdtemp()
    try:
      ar = artifacts.Artifacts(
        tempdir, iteration=0, test_name='a.b.c', intial_results_base_dir=True)
      file_rel_path = os.path.join('stdout', 'text.txt')
      with ar.CreateArtifact('artifact_name', file_rel_path) as f:
        f.write(b'contents')
      self._VerifyPathAndContents(
          tempdir, file_rel_path, b'contents', iteration=0, test_base_dir='a.b.c',
          intial_results_base_dir=True)
    finally:
      shutil.rmtree(tempdir)

  def test_file_manager_writes_file(self):
    disc = {}
    ar = artifacts.Artifacts('tmp', iteration=0, file_manager=_FakeFileManager(disc))
    file_path = os.path.join('failures', 'stderr.txt')
    with ar.CreateArtifact('artifact_name', file_path) as f:
      f.write('hello world')
    self.assertEqual(disc, {os.path.join('tmp', file_path): 'hello world'})

  def test_finds_duplicates_in_file_manager_(self):
    disc = {}
    ar = artifacts.Artifacts('tmp', iteration=0, file_manager=_FakeFileManager(disc))
    file_path = os.path.join('failures', 'stderr.txt')
    with ar.CreateArtifact('artifact1', file_path) as f:
      f.write('hello world')
    with self.assertRaises(ValueError) as ve:
      with ar.CreateArtifact('artifact2', file_path) as f:
        f.write('Goodbye world')
    self.assertIn('already exists', str(ve.exception))


class ArtifactsLinkCreationTests(unittest.TestCase):
  def test_create_link(self):
    ar = artifacts.Artifacts(None)
    ar.CreateLink('link', 'https://testsite.com')
    self.assertEqual(ar.artifacts, {'link': ['https://testsite.com']})

  def test_create_link_invalid_url(self):
    ar = artifacts.Artifacts(None)
    with self.assertRaises(ValueError):
      ar.CreateLink('link', 'https:/malformedurl.com')

  def test_create_link_non_https(self):
    ar = artifacts.Artifacts(None)
    with self.assertRaises(ValueError):
      ar.CreateLink('link', 'http://testsite.com')

  def test_create_link_newlines(self):
    ar = artifacts.Artifacts(None)
    with self.assertRaises(ValueError):
      ar.CreateLink('link', 'https://some\nbadurl.com')
