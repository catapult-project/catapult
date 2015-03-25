# Copyright 2014 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import collections
import copy
import datetime
import itertools
import logging
import random
import sys
import traceback

from telemetry.results import progress_reporter as progress_reporter_module
from telemetry.results import user_story_run
from telemetry.util import cloud_storage
from telemetry import value as value_module
from telemetry.value import failure
from telemetry.value import skip
from telemetry.value import trace


class PageTestResults(object):
  def __init__(self, output_stream=None, output_formatters=None,
               progress_reporter=None, trace_tag='', output_dir=None,
               value_can_be_added_predicate=lambda v, is_first: True):
    """
    Args:
      output_stream: The output stream to use to write test results.
      output_formatters: A list of output formatters. The output
          formatters are typically used to format the test results, such
          as CsvOutputFormatter, which output the test results as CSV.
      progress_reporter: An instance of progress_reporter.ProgressReporter,
          to be used to output test status/results progressively.
      trace_tag: A string to append to the buildbot trace name. Currently only
          used for buildbot.
      output_dir: A string specified the directory where to store the test
          artifacts, e.g: trace, videos,...
      value_can_be_added_predicate: A function that takes two arguments:
          a value.Value instance (except value.FailureValue & value.SkipValue)
          and a boolean (True when the value is part of the first result for
          the user story). It returns True if the value can be added to the
          test results and False otherwise.
    """
    # TODO(chrishenry): Figure out if trace_tag is still necessary.

    super(PageTestResults, self).__init__()
    self._output_stream = output_stream
    self._progress_reporter = (
        progress_reporter if progress_reporter is not None
        else progress_reporter_module.ProgressReporter())
    self._output_formatters = (
        output_formatters if output_formatters is not None else [])
    self._trace_tag = trace_tag
    self._output_dir = output_dir
    self._value_can_be_added_predicate = value_can_be_added_predicate

    self._current_page_run = None
    self._all_page_runs = []
    self._all_user_stories = set()
    self._representative_value_for_each_value_name = {}
    self._all_summary_values = []
    self._serialized_trace_file_ids_to_paths = {}
    self._pages_to_profiling_files = collections.defaultdict(list)
    self._pages_to_profiling_files_cloud_url = collections.defaultdict(list)

  def __copy__(self):
    cls = self.__class__
    result = cls.__new__(cls)
    for k, v in self.__dict__.items():
      if isinstance(v, collections.Container):
        v = copy.copy(v)
      setattr(result, k, v)
    return result

  @property
  def serialized_trace_file_ids_to_paths(self):
    return self._serialized_trace_file_ids_to_paths

  @property
  def pages_to_profiling_files_cloud_url(self):
    return self._pages_to_profiling_files_cloud_url

  @property
  def all_page_specific_values(self):
    values = []
    for run in self._all_page_runs:
      values += run.values
    if self._current_page_run:
      values += self._current_page_run.values
    return values

  @property
  def all_summary_values(self):
    return self._all_summary_values

  @property
  def current_page(self):
    assert self._current_page_run, 'Not currently running test.'
    return self._current_page_run.user_story

  @property
  def current_page_run(self):
    assert self._current_page_run, 'Not currently running test.'
    return self._current_page_run

  @property
  def all_page_runs(self):
    return self._all_page_runs

  @property
  def pages_that_succeeded(self):
    """Returns the set of pages that succeeded."""
    pages = set(run.user_story for run in self.all_page_runs)
    pages.difference_update(self.pages_that_failed)
    return pages

  @property
  def pages_that_failed(self):
    """Returns the set of failed pages."""
    failed_pages = set()
    for run in self.all_page_runs:
      if run.failed:
        failed_pages.add(run.user_story)
    return failed_pages

  @property
  def failures(self):
    values = self.all_page_specific_values
    return [v for v in values if isinstance(v, failure.FailureValue)]

  @property
  def skipped_values(self):
    values = self.all_page_specific_values
    return [v for v in values if isinstance(v, skip.SkipValue)]

  def _GetStringFromExcInfo(self, err):
    return ''.join(traceback.format_exception(*err))

  def CleanUp(self):
    """Clean up any TraceValues contained within this results object."""
    for run in self._all_page_runs:
      for v in run.values:
        if isinstance(v, trace.TraceValue):
          v.CleanUp()
          run.values.remove(v)

  def __enter__(self):
    return self

  def __exit__(self, _, __, ___):
    self.CleanUp()

  def WillRunPage(self, page):
    assert not self._current_page_run, 'Did not call DidRunPage.'
    self._current_page_run = user_story_run.UserStoryRun(page)
    self._progress_reporter.WillRunPage(self)

  def DidRunPage(self, page):  # pylint: disable=W0613
    """
    Args:
      page: The current page under test.
    """
    assert self._current_page_run, 'Did not call WillRunPage.'
    self._progress_reporter.DidRunPage(self)
    self._all_page_runs.append(self._current_page_run)
    self._all_user_stories.add(self._current_page_run.user_story)
    self._current_page_run = None

  def AddValue(self, value):
    assert self._current_page_run, 'Not currently running test.'
    self._ValidateValue(value)
    is_first_result = (
      self._current_page_run.user_story not in self._all_user_stories)
    if not (isinstance(value, skip.SkipValue) or
            isinstance(value, failure.FailureValue) or
            self._value_can_be_added_predicate(value, is_first_result)):
      return
    # TODO(eakuefner/chrishenry): Add only one skip per pagerun assert here
    self._current_page_run.AddValue(value)
    self._progress_reporter.DidAddValue(value)

  def AddProfilingFile(self, page, file_handle):
    self._pages_to_profiling_files[page].append(file_handle)

  def AddSummaryValue(self, value):
    assert value.page is None
    self._ValidateValue(value)
    self._all_summary_values.append(value)

  def _ValidateValue(self, value):
    assert isinstance(value, value_module.Value)
    if value.name not in self._representative_value_for_each_value_name:
      self._representative_value_for_each_value_name[value.name] = value
    representative_value = self._representative_value_for_each_value_name[
        value.name]
    assert value.IsMergableWith(representative_value)

  def PrintSummary(self):
    self._progress_reporter.DidFinishAllTests(self)

    # Only serialize the trace if output_format is json.
    from telemetry.results import json_output_formatter
    if (self._output_dir and
        any(isinstance(o, json_output_formatter.JsonOutputFormatter)
            for o in self._output_formatters)):
      self._SerializeTracesToDirPath(self._output_dir)
    for output_formatter in self._output_formatters:
      output_formatter.Format(self)

  def FindPageSpecificValuesForPage(self, page, value_name):
    values = []
    for value in self.all_page_specific_values:
      if value.page == page and value.name == value_name:
        values.append(value)
    return values

  def FindAllPageSpecificValuesNamed(self, value_name):
    values = []
    for value in self.all_page_specific_values:
      if value.name == value_name:
        values.append(value)
    return values

  def FindAllTraceValues(self):
    values = []
    for value in self.all_page_specific_values:
      if isinstance(value, trace.TraceValue):
        values.append(value)
    return values

  def _SerializeTracesToDirPath(self, dir_path):
    """ Serialize all trace values to files in dir_path and return a list of
    file handles to those files. """
    for value in self.FindAllTraceValues():
      fh = value.Serialize(dir_path)
      self._serialized_trace_file_ids_to_paths[fh.id] = fh.GetAbsPath()

  def UploadTraceFilesToCloud(self, bucket):
    for value in self.FindAllTraceValues():
      value.UploadToCloud(bucket)

  def UploadProfilingFilesToCloud(self, bucket):
    for page, file_handle_list in self._pages_to_profiling_files.iteritems():
      for file_handle in file_handle_list:
        remote_path = ('profiler-file-id_%s-%s%-d%s' % (
            file_handle.id,
            datetime.datetime.now().strftime('%Y-%m-%d_%H-%M-%S'),
            random.randint(1, 100000),
            file_handle.extension))
        try:
          cloud_url = cloud_storage.Insert(
              bucket, remote_path, file_handle.GetAbsPath())
          sys.stderr.write(
              'View generated profiler files online at %s for page %s\n' %
              (cloud_url, page.display_name))
          self._pages_to_profiling_files_cloud_url[page].append(cloud_url)
        except cloud_storage.PermissionError as e:
          logging.error('Cannot upload profiling files to cloud storage due to '
                        ' permission error: %s' % e.message)
