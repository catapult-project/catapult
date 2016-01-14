# Copyright 2015 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.


class Failure(object):

  def __init__(self, job_guid, function_handle_guid, trace_guid,
               failure_type_name, description, stack):
    self.job_guid = job_guid
    self.function_handle_guid = function_handle_guid
    self.trace_guid = trace_guid
    self.failure_type_name = failure_type_name
    self.description = description
    self.stack = stack

  def AsDict(self):
    return {
        'job_guid': self.job_guid,
        'function_handle_guid': self.function_handle_guid,
        'trace_guid': self.trace_guid,
        'failure_type_name': self.failure_type_name,
        'description': self.description,
        'stack': self.stack
    }

  @staticmethod
  def FromDict(failure_dict):
    return Failure(failure_dict['job_guid'],
                   failure_dict['function_handle_guid'],
                   failure_dict['trace_guid'],
                   failure_dict['failure_type_name'],
                   failure_dict['description'], failure_dict['stack'])
