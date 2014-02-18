#!/usr/bin/env python
# Copyright (c) 2014 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import base64
import optparse
import parse_deps
import sys
import os
import re

srcdir = os.path.abspath(os.path.join(os.path.dirname(__file__),
                                      "..", "..", "..", "src"))

html_warning_message = """


<!--
WARNING: This file is auto generated.

         Do not edit directly.
-->
"""

js_warning_message = """
// Copyright (c) 2014 The Chromium Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

/* WARNING: This file is auto generated.
 *
 * Do not edit directly.
 */
"""

css_warning_message = """
/* Copyright (c) 2014 The Chromium Authors. All rights reserved.
 * Use of this source code is governed by a BSD-style license that can be
 * found in the LICENSE file. */

/* WARNING: This file is auto-generated.
 *
 * Do not edit directly.
 */
"""

def GenerateCSS(load_sequence):
  style_sheet_chunks = [css_warning_message, '\n']
  for module in load_sequence:
    for style_sheet in module.style_sheets:
      style_sheet_chunks.append(style_sheet.contents_with_inlined_images)
      style_sheet_chunks.append('\n')
  return ''.join(style_sheet_chunks)

def GenerateJS(load_sequence, include_html_templates=True):
  js_chunks = [js_warning_message, '\n']
  js_chunks.append("window.FLATTENED = {};\n")
  js_chunks.append("window.FLATTENED_RAW_SCRIPTS = {};\n")

  for module in load_sequence:
    for dependent_raw_scripts in module.dependent_raw_scripts:
      js_chunks.append("window.FLATTENED_RAW_SCRIPTS['%s'] = true;\n" %
        dependent_raw_script.resource.unix_style_relative_path)
    js_chunks.append( "window.FLATTENED['%s'] = true;\n" % module.name)

  if include_html_templates:
    html_encoded = base64.b64encode(
        GenerateHTMLForCombinedTemplates(load_sequence))
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

def GenerateDepsJS(load_sequence, project):
  chunks = [js_warning_message, '\n']
  loader = load_sequence[0].loader
  for module in loader.loaded_modules.values():
    chunks.append("tvcm.setResourceFileName('%s','%s');\n" % (
        module.name, module.resource.relative_path))

  for module in load_sequence:
    for dependent_module in module.dependent_modules:
      chunks.append("tvcm.addModuleDependency('%s','%s');\n" % (
          module.name, dependent_module.name));

    for dependent_raw_script in module.dependent_raw_scripts:
      relative_path = dependent_raw_script.resource.relative_path
      chunks.append(
          "tvcm.addModuleRawScriptDependency('%s','%s');\n" % (
           module.name, relative_path));

    for style_sheet in module.style_sheets:
      chunks.append("tvcm.addModuleStylesheet('%s','%s');\n" % (
          module.name, style_sheet.name));
  return "".join(chunks)

def GenerateHTMLForCombinedTemplates(load_sequence):
  chunks = []
  for module in load_sequence:
    for html_template in module.html_templates:
      chunks.append(html_template.contents)
  return "\n".join(chunks)

class ExtraScript(object):
  def __init__(self, script_id, text_content, content_type=None):
    if script_id != None:
      assert script_id[0] != '#'
    assert isinstance(text_content, basestring)
    self.script_id = script_id
    self.text_content = text_content
    self.content_type = content_type

def GenerateStandaloneHTMLFile(load_sequence,
                               title,
                               flattened_js_url=None,
                               extra_scripts=None):
  extra_scripts = extra_scripts or []

  head_html_chunks = []
  head_html_chunks.append("<style>")
  head_html_chunks.append(GenerateCSS(load_sequence))
  head_html_chunks.append("</style>")
  head_html_chunks.append(GenerateHTMLForCombinedTemplates(load_sequence))
  if flattened_js_url:
    head_html_chunks.append('<script src="%s"></script>' % flattened_js_url)
  else:
    head_html_chunks.append('<script>')
    head_html_chunks.append(GenerateJS(load_sequence,
                                        include_html_templates=False))
    head_html_chunks.append('</script>')

  for extra_script in extra_scripts:
    attrs = []
    if extra_script.script_id:
      attrs.append('id="%s"' % extra_script.script_id)
    if extra_script.content_type:
      attrs.append('content-type="%s"' % extra_script.content_type)
    if len(attrs) > 0:
      head_html_chunks.append('<script %s>' % ' '.join(attrs))
    else:
      head_html_chunks.append('<script>')
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
