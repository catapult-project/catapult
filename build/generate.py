#!/usr/bin/env python
# Copyright (c) 2012 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import base64
import optparse
import parse_deps
import sys
import os
import re

srcdir = os.path.abspath(os.path.join(os.path.dirname(__file__), "../src"))

html_warning_message = """


<!--
WARNING: This file is auto generated.

         Do not edit directly.
-->
"""

js_warning_message = """
// Copyright (c) 2013 The Chromium Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

/* WARNING: This file is auto generated.
 *
 * Do not edit directly.
 */
"""

css_warning_message = """
/* Copyright (c) 2013 The Chromium Authors. All rights reserved.
 * Use of this source code is governed by a BSD-style license that can be
 * found in the LICENSE file. */

/* WARNING: This file is auto-generated.
 *
 * Do not edit directly.
 */
"""

def generate_css(load_sequence):
  style_sheet_chunks = [css_warning_message, '\n']
  for module in load_sequence:
    for style_sheet in module.style_sheets:
      style_sheet_chunks.append("""%s\n""" % style_sheet.contents)

  # Borrowed from grit html_format.py.
  def InlineUrl(m):
    filename = m.group('filename')
    idx = filename.index('/images')
    filename = "%s%s" % (srcdir, filename[idx:])
    ext = filename[filename.rindex('.') + 1:]

    with open(filename, 'rb') as f:
      data = f.read();
    data = base64.standard_b64encode(data)

    return "url(data:image/%s;base64,%s)" % (ext, data)

  full_style_sheet = ''.join(style_sheet_chunks)
  # I'm assuming we only have url()'s associated with images
  return re.sub('url\((?P<quote>"|\'|)(?P<filename>[^"\'()]*)(?P=quote)\)',
                lambda m: InlineUrl(m),
                full_style_sheet)

def generate_js(load_sequence, include_html_templates=True):
  js_chunks = [js_warning_message, '\n']
  js_chunks.append("window.FLATTENED = {};\n")
  js_chunks.append("window.FLATTENED_RAW_SCRIPTS = {};\n")

  for module in load_sequence:
    for dependent_raw_script_name in module.dependent_raw_script_names:
      js_chunks.append("window.FLATTENED_RAW_SCRIPTS['%s'] = true;\n" %
        dependent_raw_script_name)
    js_chunks.append( "window.FLATTENED['%s'] = true;\n" % module.name)

  if include_html_templates:
    html_encoded = base64.b64encode(
        generate_html_for_combined_templates(load_sequence))
    js_chunks.append("var templateData_ = window.atob('" +
                     html_encoded + "');\n");
    js_chunks.append("var templateElem_ = document.createElement('div');\n");
    js_chunks.append("templateElem_.innerHTML = templateData_;\n");
    js_chunks.append("while (templateElem_.hasChildNodes()) {\n");
    js_chunks.append("  document.head.appendChild(" +
                     "templateElem_.removeChild(templateElem_.firstChild));\n");
    js_chunks.append("}\n\n");

  for module in load_sequence:
    for dependent_raw_script in module.dependent_raw_scripts:
      js_chunks.append(dependent_raw_script.contents)
      js_chunks.append('\n')
    js_chunks.append(module.contents)
    js_chunks.append("\n")

  return ''.join(js_chunks)

def generate_deps_js(load_sequence):
  chunks = [js_warning_message, '\n']
  for module in load_sequence:
    for dependent_module_name in module.dependent_module_names:
      chunks.append("base.addModuleDependency('%s','%s');\n" % (
          module.name, dependent_module_name));

    for dependent_raw_script_name in module.dependent_raw_script_names:
      chunks.append(
          "base.addModuleRawScriptDependency('%s','%s');\n" % (
          module.name, dependent_raw_script_name));

    for style_sheet in module.style_sheets:
      chunks.append("base.addModuleStylesheet('%s','%s');\n" % (
          module.name, style_sheet.name));
  return "".join(chunks)

def generate_html_for_combined_templates(load_sequence):
  chunks = []
  for module in load_sequence:
    for html_template in module.html_templates:
      chunks.append(html_template.contents)
  return "\n".join(chunks)

class ExtraScript(object):
  def __init__(self, script_id, text_content, content_type=None):
    assert script_id[0] != '#'
    assert isinstance(text_content, basestring)
    self.script_id = script_id
    self.text_content = text_content
    self.content_type = content_type

def generate_standalone_html_file(load_sequence,
                                  title,
                                  flattened_js_url=None,
                                  extra_scripts=None):
  extra_scripts = extra_scripts or []

  head_html_chunks = []
  head_html_chunks.append("<style>")
  head_html_chunks.append(generate_css(load_sequence))
  head_html_chunks.append("</style>")
  head_html_chunks.append(generate_html_for_combined_templates(load_sequence))
  if flattened_js_url:
    head_html_chunks.append('<script src="%s"></script>' % flattened_js_url)
  else:
    head_html_chunks.append('<script>')
    head_html_chunks.append(generate_js(load_sequence,
                                        include_html_templates=False))
    head_html_chunks.append('</script>')

  for extra_script in extra_scripts:
    attrs = ['id="%s"' % extra_script.script_id]
    if extra_script.content_type:
      attrs.append('content-type="%s"' % extra_script.content_type)
    head_html_chunks.append('<script %s>' % ' '.join(attrs))
    head_html_chunks.append(extra_script.text_content)
    head_html_chunks.append('</script>')

  return """
<!DOCTYPE HTML>
<html>
  %s
  <head i18n-values="dir:textdirection;">
  <title>%s</title>
  %s
</head>
<body>
</body>
</html>
""" % (html_warning_message,
       title,
       '\n'.join(head_html_chunks))
