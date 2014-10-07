# Copyright (c) 2014 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import base64
import optparse
import sys
import os
import re
import StringIO

from tvcm import js_utils
from tvcm import module as module_module
from tvcm import html_generation_controller


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

def GenerateJS(load_sequence,
               use_include_tags_for_scripts=False,
               dir_for_include_tag_root=None):
  f = StringIO.StringIO()
  GenerateJSToFile(f,
                   load_sequence,
                   use_include_tags_for_scripts,
                   dir_for_include_tag_root)
  return f.getvalue()

def GenerateJSToFile(f,
                     load_sequence,
                     use_include_tags_for_scripts=False,
                     dir_for_include_tag_root=None):
  if use_include_tags_for_scripts and dir_for_include_tag_root == None:
    raise Exception('Must provide dir_for_include_tag_root')

  f.write(js_warning_message)
  f.write('\n')

  loader = load_sequence[0].loader

  polymer_script = loader.LoadRawScript('components/polymer/polymer.js')
  f.write(polymer_script.contents)

  f.write('\n')
  f.write("window._TV_IS_COMPILED = true;\n")

  for module in load_sequence:
    module.AppendJSContentsToFile(f,
                                  use_include_tags_for_scripts,
                                  dir_for_include_tag_root)

class ExtraScript(object):
  def __init__(self, script_id=None, text_content=None, content_type=None):
    if script_id != None:
      assert script_id[0] != '#'
    self.script_id = script_id
    self.text_content = text_content
    self.content_type = content_type

  def WriteToFile(self, output_file):
    attrs = []
    if self.script_id:
      attrs.append('id="%s"' % self.script_id)
    if self.content_type:
      attrs.append('content-type="%s"' % self.content_type)

    if len(attrs) > 0:
      output_file.write('<script %s>\n' % ' '.join(attrs))
    else:
      output_file.write('<script>\n')
    if self.text_content:
      output_file.write(self.text_content)
    output_file.write('</script>\n')


def GenerateStandaloneHTMLAsString(*args, **kwargs):
  f = StringIO.StringIO()
  GenerateStandaloneHTMLToFile(f, *args, **kwargs)
  return f.getvalue()

def GenerateStandaloneHTMLToFile(output_file,
                                 load_sequence,
                                 title,
                                 flattened_js_url=None,
                                 extra_scripts=None):
  extra_scripts = extra_scripts or []

  output_file.write("""<!DOCTYPE HTML>
<html>
  <head i18n-values="dir:textdirection;">
  <meta http-equiv="Content-Type" content="text/html; charset=utf-8">
  <title>%s</title>
""" % title)

  loader = load_sequence[0].loader

  written_style_sheets = set()

  class HTMLGenerationController(html_generation_controller.HTMLGenerationController):
    def __init__(self, module):
      self.module = module
    def GetHTMLForStylesheetHRef(self, href):
      resource = self.module.HRefToResource(
          href, '<link rel="stylesheet" href="%s">' % href)
      style_sheet = loader.LoadStyleSheet(resource.name)

      if style_sheet in written_style_sheets:
        return None
      written_style_sheets.add(style_sheet)

      return "<style>\n%s\n</style>" % style_sheet.contents_with_inlined_images

  for module in load_sequence:
    ctl = HTMLGenerationController(module)
    module.AppendHTMLContentsToFile(output_file, ctl)

  if flattened_js_url:
    output_file.write('<script src="%s"></script>\n' % flattened_js_url)
  else:
    output_file.write('<script>\n')
    output_file.write(GenerateJS(load_sequence))
    output_file.write('</script>\n')

  for extra_script in extra_scripts:
    extra_script.WriteToFile(output_file)

  output_file.write("""</head>
<body>
""")

  output_file.write("""</body>
</html>
""")
