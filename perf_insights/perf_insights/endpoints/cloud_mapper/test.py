# Copyright (c) 2015 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.
import os
import webapp2

from perf_insights import cloud_config


def _is_devserver():
  return os.environ.get('SERVER_SOFTWARE', '').startswith('Development')

_DEFAULT_MAPPER = """
<!DOCTYPE html>
<!--
Copyright (c) 2015 The Chromium Authors. All rights reserved.
Use of this source code is governed by a BSD-style license that can be
found in the LICENSE file.
-->
<link rel="import" href="/perf_insights/function_handle.html">
<link rel="import"
    href="/tracing/metrics/system_health/system_health_metric.html">
<link rel="import" href="/tracing/value/value.html">

<script>
tr.exportTo('pi.m', function() {

  function railMapFunction(results, runInfo, model) {
    var health = tr.metrics.sh.SystemHealthMetric.forModel(model);
    if (health === undefined) {
      return;
    }
    results.addValue(new tr.v.DictValue(runInfo, 'railScore',
                                        {overallScore: health}));
  }
  pi.FunctionRegistry.register(railMapFunction);

  return {
    railMapFunction: railMapFunction
  };
});

</script>
"""

_DEFAULT_FUNCTION = 'railMapFunction'

_FORM_HTML = """
<!DOCTYPE html>
<html>
<body>
<form action="/cloud_mapper/create" method="POST">
Mapper: <br><textarea rows="50" cols="80" name="mapper">{mapper}</textarea>
<br>
FunctionName: <br><input type="text" name="mapper_function"
    value="{mapper_function}"/>
<br>
Query: <br><input type="text" name="query" value="{query}"/>
<br>
Corpus: <br><input type="text" name="corpus" value="{corpus}"/>
<br>
<input type="submit" name="submit" value="Submit"/>
</form>
</body>
</html>
"""


class TestPage(webapp2.RequestHandler):

  def get(self):
    form_html = _FORM_HTML.format(mapper=_DEFAULT_MAPPER,
                                  mapper_function=_DEFAULT_FUNCTION,
                                  query='MAX_TRACE_HANDLES=10',
                                  corpus=cloud_config.Get().default_corpus)
    self.response.out.write(form_html)

app = webapp2.WSGIApplication([('/cloud_mapper/test', TestPage)])
