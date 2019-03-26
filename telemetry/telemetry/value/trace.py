# Copyright 2014 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import logging
import os
import shutil
import sys
import tempfile

from py_utils import cloud_storage  # pylint: disable=import-error

from telemetry.internal.util import file_handle
from telemetry import value as value_module


class TraceValue(value_module.Value):
  def __init__(self, page, trace_data, important=False, description=None,
               file_path=None, remote_path=None, upload_bucket=None,
               cloud_url=None, trace_url=None):
    """A value that contains trace data and knows how to output it.

    Adding TraceValues and outputting as JSON will produce a directory full of
    HTML files called trace_files. Outputting as chart JSON will also produce
    an index, files.html, linking to each of these files.

    Args:
      cloud_url: The URL to upload the data to. This can be None when not
                 uploading data to the cloud.
      trace_url: The URL to the trace file (typically in the local file system).
    """
    super(TraceValue, self).__init__(
        page, name='trace', units='', important=important,
        description=description, tir_label=None, grouping_keys=None)
    self._trace_data = trace_data
    self._temp_file = None
    self._file_path = file_path
    self._remote_path = remote_path
    self._upload_bucket = upload_bucket
    self._cloud_url = cloud_url
    self._serialized_file_handle = None
    self._timeline_based_metrics = None
    self._trace_url = trace_url

  @property
  def value(self):
    if self._cloud_url:
      return self._cloud_url
    elif self._serialized_file_handle:
      return self._serialized_file_handle.GetAbsPath()

  def SerializeTraceData(self):
    if not self._temp_file:
      self._temp_file = self._GetTempFileHandle(self._trace_data)

  def _GetTempFileHandle(self, trace_data):
    tf = tempfile.NamedTemporaryFile(delete=False, suffix='.html')
    tf.close()
    title = ''
    if self.page:
      title = self.page.name
    trace_data.Serialize(tf.name, trace_title=title)
    return file_handle.FromFilePath(tf.name)

  def __repr__(self):
    if self.page:
      page_name = self.page.name
    else:
      page_name = 'None'
    return 'TraceValue(%r, %r)' % (page_name, self.name)

  def SetTimelineBasedMetrics(self, metrics):
    assert not self._temp_file, 'Trace data should not already be serialized.'
    self._timeline_based_metrics = metrics

  def CleanUp(self):
    """Cleans up tempfile after it is no longer needed.

    A cleaned up TraceValue cannot be used for further operations. CleanUp()
    may be called more than once without error.
    """
    if self._trace_data:
      self._trace_data.CleanUpAllTraces()
      self._trace_data = None

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
    return self._temp_file is None and self._trace_data is None

  @property
  def is_serialized(self):
    return self._temp_file is not None

  @property
  def trace_url(self):
    return self._trace_url

  @property
  def timeline_based_metric(self):
    return self._timeline_based_metrics

  @property
  def filename(self):
    assert self._temp_file, "Trace data must be serialized."
    return self._temp_file.GetAbsPath()

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
    if self._file_path:
      d['file_path'] = self._file_path
    if self._cloud_url:
      d['cloud_url'] = self._cloud_url
    return d

  def Serialize(self):
    if self._temp_file is None:
      raise ValueError('Tried to serialize nonexistent trace.')
    if self._file_path is None:
      raise ValueError('Serialize requires file_path.')
    shutil.copy(self._temp_file.GetAbsPath(), self._file_path)
    self._serialized_file_handle = file_handle.FromFilePath(self._file_path)
    return self._serialized_file_handle

  def UploadToCloud(self):
    if self._temp_file is None:
      raise ValueError('Tried to upload nonexistent trace to Cloud Storage.')
    try:
      if self._serialized_file_handle:
        fh = self._serialized_file_handle
      else:
        fh = self._temp_file
      cloud_storage.Insert(
          self._upload_bucket, self._remote_path, fh.GetAbsPath())
      sys.stderr.write(
          'View generated trace files online at %s for story %s\n' %
          (self._cloud_url, self.page.name if self.page else 'unknown'))
      return self._cloud_url
    except cloud_storage.PermissionError as e:
      logging.error('Cannot upload trace files to cloud storage due to '
                    ' permission error: %s' % e.message)
