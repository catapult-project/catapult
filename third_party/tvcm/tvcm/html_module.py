# Copyright 2014 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import os
import re

from tvcm import module
from tvcm import js_module
from tvcm import js_utils
from tvcm import strip_js_comments
from tvcm import parse_html_deps

def IsHTMLResourceTheModuleGivenConflictingResourceNames(
    js_resource, html_resource):
  return 'polymer-element' in html_resource.contents

class HTMLModule(module.Module):
  @property
  def _module_dir_name(self):
    return os.path.dirname(self.resource.absolute_path)

  def Parse(self):
    try:
      parser_results = parse_html_deps.HTMLModuleParser().Parse(self.contents)
    except Exception, ex:
      raise Exception('While parsing %s: %s' % (self.name, str(ex)))
    self.dependency_metadata = Parse(self.loader,
                                     self.name, self._module_dir_name,
                                     parser_results)
    self._parser_results = parser_results

  def Load(self):
    super(HTMLModule, self).Load()

    reachable_names = set([m.name
                           for m in self.all_dependent_modules_recursive])
    if 'polymer-element' in self.contents or \
       'Polymer(' in self.contents:
      if 'tvcm.polymer' not in reachable_names:
        raise Exception('%s:7:Does not have a dependency on tvcm.polymer' % \
                        os.path.relpath(self.resource.absolute_path))

    if 'tvcm.exportTo' in self.contents:
      if 'tvcm' not in reachable_names:
        raise Exception('%s:7:Does not have a dependency on tvcm' % os.path.relpath(self.resource.absolute_path))

    """
    if 'tvcm.testSuite' in self.contents or 'tvcm.unittest.testSuite' in self.contents:
      if 'tvcm.unittest' not in reachable_names:
        raise Exception('%s:7:Does not have a dependency on tvcm.unittest' % os.path.relpath(self.resource.absolute_path))
    """

  def GetTVCMDepsModuleType(self):
    return 'tvcm.HTML_MODULE_TYPE'

  def AppendJSContentsToFile(self,
                             f,
                             use_include_tags_for_scripts,
                             dir_for_include_tag_root):
    super(HTMLModule, self).AppendJSContentsToFile(f,
                                                   use_include_tags_for_scripts,
                                                   dir_for_include_tag_root)
    for inline_script_contents in self._parser_results.scripts_inline:
      f.write(js_utils.EscapeJSIfNeeded(inline_script_contents))
      f.write("\n")

  def AppendHTMLContentsToFile(self, f, ctl):
    super(HTMLModule, self).AppendHTMLContentsToFile(f, ctl)
    for piece in self._parser_results.YieldHTMLInPieces(ctl):
      f.write(piece)

  def HRefToResource(self, href, tag_for_err_msg):
    return _HRefToResource(self.loader, self.name, self._module_dir_name,
                           href, tag_for_err_msg)


def _HRefToResource(loader, module_name, module_dir_name, href, tag_for_err_msg):
  if href[0] == '/':
    resource = loader.FindResourceGivenRelativePath(href[1:])
  else:
    abspath = os.path.normpath(os.path.join(
        module_dir_name, href))
    resource = loader.FindResourceGivenAbsolutePath(abspath)

  if not resource:
    raise module.DepsException('In %s, the %s cannot be loaded because ' \
                    'it is not in the search path' % (module_name, tag_for_err_msg))
  try:
    resource_contents = resource.contents
  except:
    raise module.DepsException('In %s, %s points at a nonexistant file ' % (
      module_name,
      tag_for_err_msg))
  return resource


def Parse(loader, module_name, module_dir_name, parser_results):
  if parser_results.has_decl == False:
    raise Exception('%s must have <!DOCTYPE html>' % module_name)

  res = module.ModuleDependencyMetadata()

  # External script references..
  for href in parser_results.scripts_external:
    resource = _HRefToResource(loader, module_name, module_dir_name,
                               href,
                               tag_for_err_msg='<script src="%s">' % href)
    res.dependent_raw_script_relative_paths.append(resource.unix_style_relative_path)

  # External imports. Mostly the same as <script>, but we know its a module.
  for href in parser_results.imports:
    if not href.endswith('.html'):
      raise Exception('In %s, the <link rel="import" href="%s"> must point at a ' \
                      'file with an html suffix' % (module_name, href))

    resource = _HRefToResource(loader, module_name, module_dir_name,
                               href,
                               tag_for_err_msg='<link rel="import" href="%s">' % href)
    res.dependent_module_names.append(resource.name)

  # Search the inline scripts for tvcm commands
  for inline_script_contents in parser_results.scripts_inline:
    stripped_text = strip_js_comments.StripJSComments(inline_script_contents)
    try:
      js_module.ValidateUsesStrictMode('_', stripped_text)
    except:
      raise Exception('%s has an inline script tag that is missing ' \
                      'a \'use strict\' directive.' % module_name)

  # Style sheets
  for href in parser_results.stylesheets:
    resource = _HRefToResource(loader, module_name, module_dir_name,
                               href,
                               tag_for_err_msg='<link rel="stylesheet" href="%s">' % href)
    res.style_sheet_names.append(resource.name)

  return res
