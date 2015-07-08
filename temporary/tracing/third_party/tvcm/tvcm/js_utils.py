# Copyright 2014 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

def EscapeJSIfNeeded(js):
  return js.replace("</script>", "<\/script>")

def ValidateUsesStrictMode(module_name, stripped_text):
  """Check that the first non-empty line is 'use strict';.

  Args:
    stripped_text: Javascript source code with comments stripped out.

  Raises:
    DepsException: This file doesn't use strict mode.
  """
  lines = stripped_text.split('\n')
  for line in lines:
    line = line.strip()
    if len(line.strip()) == 0:
      continue
    if """'use strict';""" in line.strip():
      break
    raise module.DepsException('%s must use strict mode' % module_name)

