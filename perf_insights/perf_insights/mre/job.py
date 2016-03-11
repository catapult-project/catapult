# Copyright 2015 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.
import os
import uuid

import perf_insights_project
from perf_insights import function_handle

_DEFAULT_REDUCE_FILE_PATH = os.path.join(
    perf_insights_project.PerfInsightsProject.perf_insights_src_path,
    'reducers', 'default_reduce_function.html')
_DEFAULT_REDUCE_FUNCTION_NAME = 'defaultReduceFunction'


class Job(object):

  def __init__(self, map_function_handle, reduce_function_handle=None,
               guid=uuid.uuid4()):
    assert map_function_handle is not None

    self._map_function_handle = map_function_handle
    self._reduce_function_handle = reduce_function_handle
    if not reduce_function_handle:
      self._reduce_function_handle = self._CreateDefaultReduceHandle()
    self._guid = guid

  @property
  def guid(self):
    return self._guid

  @property
  def map_function_handle(self):
    return self._map_function_handle

  @property
  def reduce_function_handle(self):
    return self._reduce_function_handle

  def _CreateDefaultReduceHandle(self):
    module = function_handle.ModuleToLoad(filename=_DEFAULT_REDUCE_FILE_PATH)
    handle = function_handle.FunctionHandle(
        modules_to_load=[module], function_name=_DEFAULT_REDUCE_FUNCTION_NAME)
    return handle

  def AsDict(self):
    values_dict = {
        'map_function_handle': self._map_function_handle.AsDict(),
        'reduce_function_handle': self._reduce_function_handle.AsDict(),
        'guid': str(self._guid)
    }
    return values_dict

  @staticmethod
  def FromDict(job_dict):
    reduce_function_handle = None
    if job_dict.has_key('reduce_function_handle'):
      reduce_function_handle = function_handle.FunctionHandle.FromDict(
            job_dict['reduce_function_handle'])

    return Job(
        function_handle.FunctionHandle.FromDict(
            job_dict['map_function_handle']), reduce_function_handle)
