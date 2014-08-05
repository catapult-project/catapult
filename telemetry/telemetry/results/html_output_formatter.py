# Copyright 2014 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import datetime
import json
import logging
import os
import re

from telemetry.core import util
from telemetry.results import buildbot_output_formatter
from telemetry.util import cloud_storage

util.AddDirToPythonPath(util.GetChromiumSrcDir(), 'build', 'util')
import lastchange  # pylint: disable=F0401


_TEMPLATE_HTML_PATH = os.path.join(
    util.GetTelemetryDir(), 'support', 'html_output', 'results-template.html')
_PLUGINS = [('third_party', 'flot', 'jquery.flot.min.js'),
            ('third_party', 'WebKit', 'PerformanceTests', 'resources',
             'jquery.tablesorter.min.js'),
            ('third_party', 'WebKit', 'PerformanceTests', 'resources',
             'statistics.js')]
_UNIT_JSON = ('tools', 'perf', 'unit-info.json')


# TODO(chrishenry): This should not really extend BuildbotOutputFormatter.
# Leaving as-is now since we are going to move HtmlOutputFormatter to be
# based on JSON anyway.
class HtmlOutputFormatter(buildbot_output_formatter.BuildbotOutputFormatter):
  def __init__(self, output_stream, metadata, reset_results, upload_results,
      browser_type, results_label=None, trace_tag=''):
    # Pass output_stream=None so that we blow up if
    # BuildbotOutputFormatter ever use the output_stream.
    super(HtmlOutputFormatter, self).__init__(None, trace_tag)
    self._metadata = metadata
    self._reset_results = reset_results
    self._upload_results = upload_results
    self._html_output_stream = output_stream
    self._existing_results = self._ReadExistingResults(output_stream)
    self._result = {
        'buildTime': self._GetBuildTime(),
        'revision': self._GetRevision(),
        'label': results_label,
        'platform': browser_type,
        'tests': {}
        }

  def _GetBuildTime(self):
    def _DatetimeInEs5CompatibleFormat(dt):
      return dt.strftime('%Y-%m-%dT%H:%M:%S.%f')
    return _DatetimeInEs5CompatibleFormat(datetime.datetime.utcnow())

  def _GetRevision(self):
    return lastchange.FetchVersionInfo(None).revision

  def _GetHtmlTemplate(self):
    with open(_TEMPLATE_HTML_PATH) as f:
      return f.read()

  def _GetPlugins(self):
    plugins = ''
    for p in _PLUGINS:
      with open(os.path.join(util.GetChromiumSrcDir(), *p)) as f:
        plugins += f.read()
    return plugins

  def _GetUnitJson(self):
    with open(os.path.join(util.GetChromiumSrcDir(), *_UNIT_JSON)) as f:
      return f.read()

  def _ReadExistingResults(self, output_stream):
    results_html = output_stream.read()
    if self._reset_results or not results_html:
      return []
    m = re.search(
        '^<script id="results-json" type="application/json">(.*?)</script>$',
        results_html, re.MULTILINE | re.DOTALL)
    if not m:
      logging.warn('Failed to extract previous results from HTML output')
      return []
    return json.loads(m.group(1))[:512]

  def _SaveResults(self, results):
    self._html_output_stream.seek(0)
    self._html_output_stream.write(results)
    self._html_output_stream.truncate()

  def _PrintPerfResult(self, measurement, trace, values, units,
                       result_type='default'):
    metric_name = measurement
    if trace != measurement:
      metric_name += '.' + trace
    self._result['tests'].setdefault(self._test_name, {})
    self._result['tests'][self._test_name].setdefault('metrics', {})
    self._result['tests'][self._test_name]['metrics'][metric_name] = {
        'current': values,
        'units': units,
        'important': result_type == 'default'
        }

  @property
  def _test_name(self):
    return self._metadata.name

  def GetResults(self):
    return self._result

  def GetCombinedResults(self):
    all_results = list(self._existing_results)
    all_results.append(self.GetResults())
    return all_results

  def Format(self, page_test_results):
    super(HtmlOutputFormatter, self).Format(page_test_results)

    html = self._GetHtmlTemplate()
    html = html.replace('%json_results%', json.dumps(self.GetCombinedResults()))
    html = html.replace('%json_units%', self._GetUnitJson())
    html = html.replace('%plugins%', self._GetPlugins())
    self._SaveResults(html)

    if self._upload_results:
      file_path = os.path.abspath(self._html_output_stream.name)
      file_name = 'html-results/results-%s' % datetime.datetime.now().strftime(
          '%Y-%m-%d_%H-%M-%S')
      cloud_storage.Insert(cloud_storage.PUBLIC_BUCKET, file_name, file_path)
      print
      print ('View online at '
          'http://storage.googleapis.com/chromium-telemetry/%s' % file_name)
    print
    print 'View result at file://%s' % os.path.abspath(
        self._html_output_stream.name)
