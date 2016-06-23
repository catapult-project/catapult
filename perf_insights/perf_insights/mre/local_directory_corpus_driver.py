# Copyright (c) 2015 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.
import os

from perf_insights.mre import corpus_driver
from perf_insights.mre import file_handle


def _GetFilesIn(basedir):
  data_files = []
  for dirpath, dirnames, filenames in os.walk(basedir, followlinks=True):
    new_dirnames = [d for d in dirnames if not d.startswith('.')]
    del dirnames[:]
    dirnames += new_dirnames
    for f in filenames:
      if f.startswith('.'):
        continue
      if f == 'README.md':
        continue
      full_f = os.path.join(dirpath, f)
      rel_f = os.path.relpath(full_f, basedir)
      data_files.append(rel_f)

  data_files.sort()
  return data_files


def _GetTagsForRelPath(relpath):
  # Tags.
  sub_dir = os.path.dirname(relpath)
  if len(sub_dir) == 0:
    return []
  parts = sub_dir.split(os.sep)
  return [p for p in parts if len(p) > 0]


def _GetMetadataForFilename(base_directory, filename):
  relpath = os.path.relpath(filename, base_directory)
  tags = _GetTagsForRelPath(relpath)

  metadata = {'tags': tags}

  # TODO(nduca): Add modification time to metadata.
  return metadata


def _DefaultUrlResover(abspath):
  return 'file:///%s' % abspath


class LocalDirectoryCorpusDriver(corpus_driver.CorpusDriver):

  def __init__(self, trace_directory, url_resolver=_DefaultUrlResover):
    self.directory = trace_directory
    self.url_resolver = url_resolver

  @staticmethod
  def CheckAndCreateInitArguments(parser, args):
    trace_dir = os.path.abspath(os.path.expanduser(args.trace_directory))
    if not os.path.exists(trace_dir):
      parser.error('Trace directory does not exist')
      return None
    return {'trace_directory': trace_dir}

  @staticmethod
  def AddArguments(parser):
    parser.add_argument(
        '--trace_directory',
        help='Local directory containing traces to process.')

  def GetTraceHandlesMatchingQuery(self, query):
    trace_handles = []

    files = _GetFilesIn(self.directory)
    for rel_filename in files:
      filename = os.path.join(self.directory, rel_filename)
      metadata = _GetMetadataForFilename(self.directory, filename)

      if not query.Eval(metadata, len(trace_handles)):
        continue

      url = self.url_resolver(filename)
      if url is None:
        url = _DefaultUrlResover(filename)

      th = file_handle.URLFileHandle(url, 'file://' + filename)
      trace_handles.append(th)

    return trace_handles

