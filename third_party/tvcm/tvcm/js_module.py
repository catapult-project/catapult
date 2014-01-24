# Copyright 2014 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.
"""This module contains the Module class and other classes for resources.

The Module class represents a module in the trace viewer system. A module has
a name, and may require a variety of other resources, such as stylesheets,
template objects, raw javascript, or other modules.

Other resources include HTML templates, raw javascript files, and stylesheets.
"""

import os
import re

from tvcm import module
from tvcm import strip_js_comments

class JSModule(module.Module):
  """Represents a javascript-based module.
  """
  def __init__(self, loader, name, filename):
    super(JSModule, self).__init__(loader, name, filename)

  @staticmethod
  def html_contents_is_polymer_module(contents):
    return '<polymer-component>' in contents

  def parse(self):
    stripped_text = strip_js_comments.strip_js_comments(self.contents)
    validate_uses_strict_mode(self.name, stripped_text)
    self.dependency_metadata = parse(self.name, stripped_text)


def validate_uses_strict_mode(module_name, stripped_text):
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
    if line.strip() == """'use strict';""":
      break
    raise module.DepsException('%s must use strict mode' % module_name)


def parse(module_name, stripped_text):
  """Parses the base.require* lines in the module and returns module.ModuleDependencyMetadata.

  Args:
    stripped_text: Javascript source code with comments stripped out.

  Raises:
    DepsException: The name of a resource was not formatted properly.
  """
  res = module.ModuleDependencyMetadata()
  if not module_name:
    raise Exception("Module.name must be set.")

  rest = stripped_text
  while True:
    # Search for require statements in the rest of the file.
    m_r = re.search("""base\s*\.\s*require\((["'])(.+?)\\1\)""",
                    rest, re.DOTALL)
    m_s = re.search("""base\s*\.\s*requireStylesheet\((["'])(.+?)\\1\)""",
                    rest, re.DOTALL)
    m_t = re.search("""base\s*\.\s*requireTemplate\((["'])(.+?)\\1\)""",
                    rest, re.DOTALL)
    m_irs = re.search("""base\s*\.\s*requireRawScript\((["'])(.+?)\\1\)""",
                    rest, re.DOTALL)
    matches = [m for m in [m_r, m_s, m_t, m_irs] if m]

    # Figure out which was first.
    matches.sort(key=lambda x: x.start())
    if len(matches):
      m = matches[0]
    else:
      break

    if m == m_r:
      dependent_module_name = m.group(2)
      if '/' in dependent_module_name:
        raise module.DepsException('Slashes are not allowed in module names. '
                                   "Use '.' instead: %s" % dependent_module_name)
      if dependent_module_name.endswith('js'):
        raise module.DepsException("module names shouldn't end with .js"
                                   'The module system will append that for you: %s' %
                                   dependent_module_name)
      res.dependent_module_names.append(dependent_module_name)
    elif m == m_s:
      style_sheet_name = m.group(2)
      if '/' in style_sheet_name:
        raise module.DepsException('Slashes are not allowed in style sheet names. '
                                   "Use '.' instead: %s" % style_sheet_name)
      if style_sheet_name.endswith('.css'):
        raise module.DepsException('Style sheets should not end in .css. '
                                  'The module system will append that for you: %s' %
                                  style_sheet_name)
      res.style_sheet_names.append(style_sheet_name)
    elif m == m_t:
      html_template_name = m.group(2)
      if '/' in html_template_name:
        raise module.DepsException('Slashes are not allowed in html template names. '
                                   "Use '.' instead: %s" % html_template_name)
      if html_template_name.endswith('.html'):
        raise module.DepsException(
            'HTML templates resource names should not include extension. '
            'The module system will append that for you.' %
            html_template_name)
      res.html_template_names.append(html_template_name)
    elif m == m_irs:
      name = m.group(2)
      res.dependent_raw_script_relative_paths.append(name)

    rest = rest[m.end():]

  return res
