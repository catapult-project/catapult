# Copyright 2015 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import os
import unittest

import mock

from telemetry.internal.results import story_run
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


def TestStory(name):
  return story_module.Story(shared_state.SharedState, name=name)


class StoryRunTest(unittest.TestCase):
  def setUp(self):
    self.story = TestStory('foo')

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
    self.assertTrue(run.is_expected)
    self.assertEquals(run.failure_str, 'oops')

    run = story_run.StoryRun(self.story)
    run.AddValue(scalar.ScalarValue(
        self.story, 'a', 's', 1,
        improvement_direction=improvement_direction.UP))
    run.Skip('test', is_expected=False)
    self.assertFalse(run.ok)
    self.assertFalse(run.failed)
    self.assertTrue(run.skipped)
    self.assertFalse(run.is_expected)
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
    with tempfile_ext.NamedTemporaryDirectory() as tempdir:
      run = story_run.StoryRun(
          story=TestStory(name='http://example.com'), test_prefix='benchmark',
          output_dir=tempdir)
      with run.CreateArtifact('logs.txt') as log_file:
        log_file.write('hello\n')
      run.Finish()
      entry = run.AsDict()
      self.assertEquals(
          entry,
          {
              'testResult': {
                  'testPath': 'benchmark/http%3A%2F%2Fexample.com',
                  'status': 'PASS',
                  'isExpected': True,
                  'startTime': '2009-02-13T23:31:30.987000Z',
                  'runDuration': '10.00s',
                  'artifacts': {
                      'logs.txt' : {
                          'filePath': mock.ANY,
                          'contentType': 'text/plain'
                      }
                  }
              }
          }
      )
      # Log file is in the {output_dir}/artifacts/ directory, and file name
      # extension is preserved.
      logs_file = entry['testResult']['artifacts']['logs.txt']['filePath']
      artifacts_dir = os.path.join(tempdir, 'artifacts', '')
      self.assertTrue(logs_file.startswith(artifacts_dir))
      self.assertTrue(logs_file.endswith('.txt'))


  def testCreateArtifact(self):
    with tempfile_ext.NamedTemporaryDirectory() as tempdir:
      run = story_run.StoryRun(self.story, output_dir=tempdir)
      with run.CreateArtifact('logs.txt') as log_file:
        log_file.write('hi\n')

      artifact = run.GetArtifact('logs.txt')
      with open(artifact.local_path) as f:
        self.assertEqual(f.read(), 'hi\n')
      self.assertEqual(artifact.content_type, 'text/plain')

  def testCaptureArtifact(self):
    with tempfile_ext.NamedTemporaryDirectory() as tempdir:
      run = story_run.StoryRun(self.story, output_dir=tempdir)
      with run.CaptureArtifact('logs.txt') as log_file_name:
        with open(log_file_name, 'w') as log_file:
          log_file.write('hi\n')

      artifact = run.GetArtifact('logs.txt')
      with open(artifact.local_path) as f:
        self.assertEqual(f.read(), 'hi\n')
      self.assertEqual(artifact.content_type, 'text/plain')

  def testIterArtifacts(self):
    with tempfile_ext.NamedTemporaryDirectory() as tempdir:
      run = story_run.StoryRun(self.story, output_dir=tempdir)

      with run.CreateArtifact('log/log1.foo'):
        pass
      with run.CreateArtifact('trace/trace1.json'):
        pass
      with run.CreateArtifact('trace/trace2.json'):
        pass

      all_artifacts = list(run.IterArtifacts())
      self.assertEqual(3, len(all_artifacts))

      logs = list(run.IterArtifacts('log'))
      self.assertEqual(1, len(logs))
      # Falls back to 'application/octet-stream' due to unknown extension.
      self.assertEqual('application/octet-stream', logs[0].content_type)

      traces = list(run.IterArtifacts('trace'))
      self.assertEqual(2, len(traces))
      self.assertTrue(all(t.content_type == 'application/json' for t in traces))
