# Copyright 2014 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import datetime
import logging
import os
import random
import shutil
import sys
import tempfile

from telemetry.timeline import trace_data as trace_data_module
from telemetry.core import util
from telemetry.util import cloud_storage
from telemetry.util import file_handle
from telemetry import value as value_module

# Bring in tv module for transforming raw trace to html form.
util.AddDirToPythonPath(
    util.GetChromiumSrcDir(), 'third_party', 'trace-viewer')

from trace_viewer.build import trace2html

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
        description=description, tir_label=None)
    self._temp_file = self._GetTempFileHandle(trace_data)
    self._cloud_url = None
    self._serialized_file_handle = None

  def _GetTempFileHandle(self, trace_data):
    tf = tempfile.NamedTemporaryFile(delete=False, suffix='.html')
    if self.page:
      title = self.page.display_name
    else:
      title = ''
    trace2html.WriteHTMLForTraceDataToFile(
        [trace_data.GetEventsFor(trace_data_module.CHROME_TRACE_PART)],
        title,
        tf)
    tf.close()
    return file_handle.FromTempFile(tf)

  def __repr__(self):
    if self.page:
      page_name = self.page.url
    else:
      page_name = None
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
    # TODO(eakuefner): Implement a MultiTraceValue: a Polymer-based,
    # componentized, MultiTraceViwer-backed representation of more than one
    # trace.
    assert len(values) > 0
    return values[0]

  @classmethod
  def MergeLikeValuesFromDifferentPages(cls, values,
                                        group_by_name_suffix=False):
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
    file_name = str(self._temp_file.id) + self._temp_file.extension
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
