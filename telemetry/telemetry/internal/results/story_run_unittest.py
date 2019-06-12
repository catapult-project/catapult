# Copyright 2015 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import os
import unittest

import mock

from telemetry.internal.results import story_run
from telemetry.internal.util import file_handle
from telemetry.story import shared_state
from telemetry import story as story_module
from telemetry.value import improvement_direction
from telemetry.value import scalar

from py_utils import tempfile_ext


# splitdrive returns '' on systems which don't have drives, like linux.
ROOT_CHAR = os.path.splitdrive(__file__)[0] + os.sep
def _abs_join(*args):
  """Helper to do a path join that's an absolute path."""
  return ROOT_CHAR + os.path.join(*args)


class StoryRunTest(unittest.TestCase):
  def setUp(self):
    self.story = story_module.Story(shared_state.SharedState, name='foo')

  def testStoryRunFailed(self):
    run = story_run.StoryRun(self.story)
    run.SetFailed('abc')
    self.assertFalse(run.ok)
    self.assertTrue(run.failed)
    self.assertFalse(run.skipped)
    self.assertEquals(run.failure_str, 'abc')

    run = story_run.StoryRun(self.story)
    run.AddValue(scalar.ScalarValue(
        self.story, 'a', 's', 1,
        improvement_direction=improvement_direction.UP))
    run.SetFailed('something is wrong')
    self.assertFalse(run.ok)
    self.assertTrue(run.failed)
    self.assertFalse(run.skipped)
    self.assertEquals(run.failure_str, 'something is wrong')

  def testStoryRunSkipped(self):
    run = story_run.StoryRun(self.story)
    run.SetFailed('oops')
    run.Skip('test', is_expected=True)
    self.assertFalse(run.ok)
    self.assertFalse(run.failed)
    self.assertTrue(run.skipped)
    self.assertEquals(run.expected, 'SKIP')
    self.assertEquals(run.failure_str, 'oops')

    run = story_run.StoryRun(self.story)
    run.AddValue(scalar.ScalarValue(
        self.story, 'a', 's', 1,
        improvement_direction=improvement_direction.UP))
    run.Skip('test', is_expected=False)
    self.assertFalse(run.ok)
    self.assertFalse(run.failed)
    self.assertTrue(run.skipped)
    self.assertEquals(run.expected, 'PASS')
    self.assertEquals(run.failure_str, None)

  def testStoryRunSucceeded(self):
    run = story_run.StoryRun(self.story)
    self.assertTrue(run.ok)
    self.assertFalse(run.failed)
    self.assertFalse(run.skipped)
    self.assertEquals(run.failure_str, None)

    run = story_run.StoryRun(self.story)
    run.AddValue(scalar.ScalarValue(
        self.story, 'a', 's', 1,
        improvement_direction=improvement_direction.UP))
    self.assertTrue(run.ok)
    self.assertFalse(run.failed)
    self.assertFalse(run.skipped)
    self.assertEquals(run.failure_str, None)


  @mock.patch('telemetry.internal.results.story_run.time')
  def testAsDict(self, time_module):
    time_module.time.side_effect = [1234567890.987,
                                    1234567900.987]
    run = story_run.StoryRun(self.story)
    run.AddValue(scalar.ScalarValue(
        self.story, 'a', 's', 1,
        improvement_direction=improvement_direction.UP))
    run.Finish()
    self.assertEquals(
        run.AsDict(),
        {
            'testRun': {
                'testName': 'foo',
                'status': 'PASS',
                'startTime': '2009-02-13T23:31:30.987000Z',
                'endTime': '2009-02-13T23:31:40.987000Z'
            }
        }
    )

  def testCreateArtifact(self):
    with tempfile_ext.NamedTemporaryDirectory(
        prefix='artifact_tests') as tempdir:
      run = story_run.StoryRun(self.story, tempdir)
      with run.CreateArtifact('logs', '', '') as log_file:
        filename = log_file.name
        log_file.write('hi\n')

      with open(filename) as f:
        self.assertEqual(f.read(), 'hi\n')

  @mock.patch('telemetry.internal.results.story_run.shutil.move')
  @mock.patch('telemetry.internal.results.story_run.os.makedirs')
  def testAddArtifactBasic(self, make_patch, move_patch):
    run = story_run.StoryRun(self.story, _abs_join('foo'))

    run.AddArtifact('artifact_name', _abs_join('foo', 'artifacts', 'bar.log'))
    move_patch.assert_not_called()
    make_patch.assert_called_with(_abs_join('foo', 'artifacts'))

    self.assertEqual(run._artifacts, {
        'artifact_name': os.path.join('artifacts', 'bar.log'),
    })

  @mock.patch('telemetry.internal.results.story_run.shutil.move')
  @mock.patch('telemetry.internal.results.story_run.os.makedirs')
  def testAddArtifactNested(self, make_patch, move_patch):
    run = story_run.StoryRun(self.story, _abs_join('foo'))

    run.AddArtifact('artifact_name',
                    _abs_join('foo', 'artifacts', 'baz', 'bar.log'))
    move_patch.assert_not_called()
    make_patch.assert_called_with(_abs_join('foo', 'artifacts'))

    self.assertEqual(run._artifacts, {
        'artifact_name': os.path.join('artifacts', 'baz', 'bar.log'),
    })

  @mock.patch('telemetry.internal.results.story_run.shutil.move')
  @mock.patch('telemetry.internal.results.story_run.os.makedirs')
  def testAddArtifactFileHandle(self, make_patch, move_patch):
    run = story_run.StoryRun(self.story, _abs_join('foo'))

    run.AddArtifact('artifact_name', file_handle.FromFilePath(
        _abs_join('', 'foo', 'artifacts', 'bar.log')))
    move_patch.assert_not_called()
    make_patch.assert_called_with(_abs_join('foo', 'artifacts'))

    self.assertEqual(run._artifacts, {
        'artifact_name': os.path.join('artifacts', 'bar.log'),
    })

  @mock.patch('telemetry.internal.results.story_run.shutil.move')
  @mock.patch('telemetry.internal.results.story_run.os.makedirs')
  def testAddAndMove(self, make_patch, move_patch):
    run = story_run.StoryRun(self.story, _abs_join('foo'))

    run.AddArtifact('artifact_name', _abs_join(
        'another', 'directory', 'bar.log'))
    move_patch.assert_called_with(
        _abs_join('another', 'directory', 'bar.log'),
        _abs_join('foo', 'artifacts'))
    make_patch.assert_called_with(_abs_join('foo', 'artifacts'))

    self.assertEqual(run._artifacts, {
        'artifact_name': os.path.join('artifacts', 'bar.log'),
    })

