# Copyright 2014 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import datetime
import json
import logging
import os
import random
import shutil
import subprocess
import sys
import tempfile

from py_utils import cloud_storage  # pylint: disable=import-error

from telemetry.internal.util import file_handle
from telemetry.timeline import trace_data as trace_data_module
from telemetry import value as value_module

_TRACE2HTML_PATH = os.path.join(os.path.dirname(__file__), '..', '..', '..',
                                'tracing', 'bin', 'trace2html')


class TraceValue(value_module.Value):
  def __init__(self, page, trace_data, important=False, description=None):
    """A value that contains a TraceData object and knows how to
    output it.

    Adding TraceValues and outputting as JSON will produce a directory full of
    HTML files called trace_files. Outputting as chart JSON will also produce
    an index, files.html, linking to each of these files.
    """
    super(TraceValue, self).__init__(
        page, name='trace', units='', important=important,
        description=description, tir_label=None, grouping_keys=None)
    self._temp_file = self._GetTempFileHandle(trace_data)
    self._cloud_url = None
    self._serialized_file_handle = None

  @property
  def value(self):
    if self._cloud_url:
      return self._cloud_url
    elif self._serialized_file_handle:
      return self._serialized_file_handle.GetAbsPath()

  def _GetTraceParts(self, trace_data):
    return [(trace_data.GetTracesFor(p), p)
            for p in trace_data_module.ALL_TRACE_PARTS
            if trace_data.HasTracesFor(p)]

  @staticmethod
  def _DumpTraceToFile(trace, path):
    with open(path, 'w') as fp:
      if isinstance(trace, basestring):
        fp.write(trace)
      elif isinstance(trace, dict) or isinstance(trace, list):
        json.dump(trace, fp)
      else:
        raise TypeError('Trace is of unknown type.')

  def _GetTempFileHandle(self, trace_data):
    temp_dir = tempfile.mkdtemp()
    trace_files = []
    counter = 0
    try:
      trace_size_data = {}
      for traces_list, part in self._GetTraceParts(trace_data):
        for trace in traces_list:
          file_path = os.path.join(temp_dir, '%s.trace' % counter)
          self._DumpTraceToFile(trace, file_path)
          trace_size_data.setdefault(part, 0)
          trace_size_data[part] += os.path.getsize(file_path)
          trace_files.append(file_path)
          counter += 1
      logging.info('Trace sizes in bytes: %s', trace_size_data)
      tf = tempfile.NamedTemporaryFile(delete=False, suffix='.html')
      tf.close()
      if trace_files:
        title = ''
        if self.page:
          title = self.page.display_name
        cmd = (['python', _TRACE2HTML_PATH] + trace_files +
               ['--output', tf.name] + ['--title', title])
        subprocess.check_output(cmd)
      else:
        logging.warning('No traces to convert to html.')
      return file_handle.FromTempFile(tf)
    finally:
      shutil.rmtree(temp_dir)

  def __repr__(self):
    if self.page:
      page_name = self.page.display_name
    else:
      page_name = 'None'
    return 'TraceValue(%s, %s)' % (page_name, self.name)

  def CleanUp(self):
    """Cleans up tempfile after it is no longer needed.

    A cleaned up TraceValue cannot be used for further operations. CleanUp()
    may be called more than once without error.
    """
    if self._temp_file is None:
      return
    os.remove(self._temp_file.GetAbsPath())
    self._temp_file = None

  def __enter__(self):
    return self

  def __exit__(self, _, __, ___):
    self.CleanUp()

  @property
  def cleaned_up(self):
    return self._temp_file is None

  @property
  def filename(self):
    return self._temp_file.GetAbsPath()

  def GetBuildbotDataType(self, output_context):
    return None

  def GetBuildbotValue(self):
    return None

  def GetRepresentativeNumber(self):
    return None

  def GetRepresentativeString(self):
    return None

  @staticmethod
  def GetJSONTypeName():
    return 'trace'

  @classmethod
  def MergeLikeValuesFromSamePage(cls, values):
    assert len(values) > 0
    return values[0]

  @classmethod
  def MergeLikeValuesFromDifferentPages(cls, values):
    return None

  def AsDict(self):
    if self._temp_file is None:
      raise ValueError('Tried to serialize TraceValue without tempfile.')
    d = super(TraceValue, self).AsDict()
    if self._serialized_file_handle:
      d['file_id'] = self._serialized_file_handle.id
    if self._cloud_url:
      d['cloud_url'] = self._cloud_url
    return d

  def Serialize(self, dir_path):
    if self._temp_file is None:
      raise ValueError('Tried to serialize nonexistent trace.')
    if self.page:
      file_name = self.page.file_safe_name
    else:
      file_name = ''
    file_name += str(self._temp_file.id)
    file_name += datetime.datetime.now().strftime('%Y-%m-%d_%H-%M-%S')
    file_name += self._temp_file.extension
    file_path = os.path.abspath(os.path.join(dir_path, file_name))
    shutil.copy(self._temp_file.GetAbsPath(), file_path)
    self._serialized_file_handle = file_handle.FromFilePath(file_path)
    return self._serialized_file_handle

  def UploadToCloud(self, bucket):
    if self._temp_file is None:
      raise ValueError('Tried to upload nonexistent trace to Cloud Storage.')
    try:
      if self._serialized_file_handle:
        fh = self._serialized_file_handle
      else:
        fh = self._temp_file
      remote_path = ('trace-file-id_%s-%s-%d%s' % (
          fh.id,
          datetime.datetime.now().strftime('%Y-%m-%d_%H-%M-%S'),
          random.randint(1, 100000),
          fh.extension))
      self._cloud_url = cloud_storage.Insert(
          bucket, remote_path, fh.GetAbsPath())
      sys.stderr.write(
          'View generated trace files online at %s for page %s\n' %
          (self._cloud_url, self.page.url if self.page else 'unknown'))
      return self._cloud_url
    except cloud_storage.PermissionError as e:
      logging.error('Cannot upload trace files to cloud storage due to '
                    ' permission error: %s' % e.message)
