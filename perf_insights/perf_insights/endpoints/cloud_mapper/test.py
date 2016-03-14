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
<link rel="import" href="/tracing/value/value.html">

<script>
'use strict';

tr.exportTo('pi.m', function() {

  function testMapFunction(results, runInfo, model) {
    var someValue = 4; // Chosen by fair roll of the dice.
    results.addResult('simon', {value: someValue});
  }
  pi.FunctionRegistry.register(testMapFunction);

  return {
    testMapFunction: testMapFunction
  };
});

</script>
"""

_DEFAULT_REDUCER = """
<!DOCTYPE html>
<!--
Copyright (c) 2015 The Chromium Authors. All rights reserved.
Use of this source code is governed by a BSD-style license that can be
found in the LICENSE file.
-->

<link rel="import" href="/perf_insights/function_handle.html">

<script>
'use strict';

tr.exportTo('pi.r', function() {

  function testReduceFunction(key, mapResults) {
    return {value: mapResults[key].value};
  }

  pi.FunctionRegistry.register(testReduceFunction);

  return {
    testReduceFunction: testReduceFunction
  };
});
</script>
"""

_DEFAULT_FUNCTION = 'testMapFunction'
_DEFAULT_REDUCER_FUNCTION = 'testReduceFunction'

_FORM_HTML = """
<!DOCTYPE html>
<html>
<body>
<form action="/cloud_mapper/create" method="POST">
Mapper: <br><textarea rows="15" cols="80" name="mapper">{mapper}</textarea>
<br>
FunctionName: <br><input type="text" name="mapper_function"
    value="{mapper_function}"/>
<br>
Reducer: <br><textarea rows="15" cols="80" name="reducer">{reducer}</textarea>
<br>
ReducerName: <br><input type="text" name="reducer_function"
    value="{reducer_function}"/>
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
                                  reducer=_DEFAULT_REDUCER,
                                  reducer_function=_DEFAULT_REDUCER_FUNCTION,
                                  query='MAX_TRACE_HANDLES=10',
                                  corpus=cloud_config.Get().default_corpus)
    self.response.out.write(form_html)

app = webapp2.WSGIApplication([('/cloud_mapper/test', TestPage)])
