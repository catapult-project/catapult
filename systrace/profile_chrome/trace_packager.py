# Copyright 2014 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import codecs
import gzip
import json
import os
import shutil
import sys
import zipfile

from profile_chrome import util

_CATAPULT_DIR = os.path.join(
    os.path.dirname(os.path.abspath(__file__)), '..', '..')
sys.path.append(os.path.join(_CATAPULT_DIR, 'tracing'))
# pylint: disable=F0401
from tracing_build import trace2html


def _PackageTracesAsHtml(trace_files, html_file):
  with codecs.open(html_file, mode='w', encoding='utf-8') as f:
    trace2html.WriteHTMLForTracesToFile(trace_files, f)
  for trace_file in trace_files:
    os.unlink(trace_file)


def _CompressFile(host_file, output):
  with gzip.open(output, 'wb') as out, \
      open(host_file, 'rb') as input_file:
    out.write(input_file.read())
  os.unlink(host_file)


def _ArchiveFiles(host_files, output):
  with zipfile.ZipFile(output, 'w', zipfile.ZIP_DEFLATED) as z:
    for host_file in host_files:
      z.write(host_file)
      os.unlink(host_file)


def _MergeTracesIfNeeded(trace_files):
  if len(trace_files) <= 1:
    return trace_files
  merge_candidates = []
  for trace_file in trace_files:
    with open(trace_file) as f:
      # Try to detect a JSON file cheaply since that's all we can merge.
      if f.read(1) != '{':
        continue
      f.seek(0)
      try:
        json_data = json.load(f)
      except ValueError:
        continue
      merge_candidates.append((trace_file, json_data))
  if len(merge_candidates) <= 1:
    return trace_files

  other_files = [f for f in trace_files
                 if not f in [c[0] for c in merge_candidates]]
  merged_file, merged_data = merge_candidates[0]
  for trace_file, json_data in merge_candidates[1:]:
    for key, value in json_data.items():
      if not merged_data.get(key) or json_data[key]:
        merged_data[key] = value
    os.unlink(trace_file)

  with open(merged_file, 'w') as f:
    json.dump(merged_data, f)
  return [merged_file] + other_files


def PackageTraces(trace_files, output=None, compress=False, write_json=False):
  trace_files = _MergeTracesIfNeeded(trace_files)
  if not write_json:
    html_file = os.path.splitext(trace_files[0])[0] + '.html'
    _PackageTracesAsHtml(trace_files, html_file)
    trace_files = [html_file]

  if compress and len(trace_files) == 1:
    result = output or trace_files[0] + '.gz'
    _CompressFile(trace_files[0], result)
  elif len(trace_files) > 1:
    result = output or 'chrome-combined-trace-%s.zip' % util.GetTraceTimestamp()
    _ArchiveFiles(trace_files, result)
  elif output:
    result = output
    shutil.move(trace_files[0], result)
  else:
    result = trace_files[0]
  return result
