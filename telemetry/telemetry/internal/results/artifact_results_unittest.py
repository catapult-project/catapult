# Copyright 2017 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import mock
import os
import unittest

from telemetry.internal.results import artifact_results
from telemetry.internal.util import file_handle


# splitdrive returns '' on systems which don't have drives, like linux.
ROOT_CHAR = os.path.splitdrive(__file__)[0] + os.sep


def _abs_join(*args):
  """Helper to do a path join that's an absolute path."""
  return ROOT_CHAR + os.path.join(*args)

class ArtifactResultsUnittest(unittest.TestCase):
  @mock.patch('telemetry.internal.results.artifact_results.shutil.move')
  @mock.patch('telemetry.internal.results.artifact_results.os.makedirs')
  def testAddBasic(self, make_patch, move_patch):
    ar = artifact_results.ArtifactResults(_abs_join('foo'))

    ar.AddArtifact(
        'test', 'artifact_name', _abs_join('foo', 'artifacts', 'bar.log'))
    move_patch.assert_not_called()
    make_patch.assert_called_with(_abs_join('foo', 'artifacts'))

    self.assertEqual({k: dict(v) for k, v in ar._test_artifacts.items()}, {
        'test': {
            'artifact_name': ['bar.log'],
        }
    })

  @mock.patch('telemetry.internal.results.artifact_results.shutil.move')
  @mock.patch('telemetry.internal.results.artifact_results.os.makedirs')
  def testAddNested(self, make_patch, move_patch):
    ar = artifact_results.ArtifactResults(_abs_join('foo'))

    ar.AddArtifact('test', 'artifact_name', _abs_join(
        'foo', 'artifacts', 'baz', 'bar.log'))
    move_patch.assert_not_called()
    make_patch.assert_called_with(_abs_join('foo', 'artifacts'))

    self.assertEqual({k: dict(v) for k, v in ar._test_artifacts.items()}, {
        'test': {
            'artifact_name': [os.path.join('baz', 'bar.log')],
        }
    })

  @mock.patch('telemetry.internal.results.artifact_results.shutil.move')
  @mock.patch('telemetry.internal.results.artifact_results.os.makedirs')
  def testAddFileHandle(self, make_patch, move_patch):
    ar = artifact_results.ArtifactResults(_abs_join('foo'))

    ar.AddArtifact('test', 'artifact_name', file_handle.FromFilePath(
        _abs_join('', 'foo', 'artifacts', 'bar.log')))
    move_patch.assert_not_called()
    make_patch.assert_called_with(_abs_join('foo', 'artifacts'))

    self.assertEqual({k: dict(v) for k, v in ar._test_artifacts.items()}, {
        'test': {
            'artifact_name': ['bar.log'],
        }
    })

  @mock.patch('telemetry.internal.results.artifact_results.shutil.move')
  @mock.patch('telemetry.internal.results.artifact_results.os.makedirs')
  def testAddAndMove(self, make_patch, move_patch):
    ar = artifact_results.ArtifactResults(_abs_join('foo'))

    ar.AddArtifact('test', 'artifact_name', _abs_join(
        'another', 'directory', 'bar.log'))
    move_patch.assert_called_with(
        _abs_join('another', 'directory', 'bar.log'),
        _abs_join('foo', 'artifacts'))
    make_patch.assert_called_with(_abs_join('foo', 'artifacts'))

    self.assertEqual({k: dict(v) for k, v in ar._test_artifacts.items()}, {
        'test': {
            'artifact_name': ['bar.log'],
        }
    })

  @mock.patch('telemetry.internal.results.artifact_results.shutil.move')
  @mock.patch('telemetry.internal.results.artifact_results.os.makedirs')
  def testAddMultiple(self, make_patch, move_patch):
    ar = artifact_results.ArtifactResults(_abs_join('foo'))

    ar.AddArtifact('test', 'artifact_name', _abs_join(
        'foo', 'artifacts', 'bar.log'))
    ar.AddArtifact('test', 'artifact_name', _abs_join(
        'foo', 'artifacts', 'bam.log'))
    move_patch.assert_not_called()
    make_patch.assert_called_with(_abs_join('foo', 'artifacts'))

    self.assertEqual({k: dict(v) for k, v in ar._test_artifacts.items()}, {
        'test': {
            'artifact_name': ['bar.log', 'bam.log'],
        }
    })
