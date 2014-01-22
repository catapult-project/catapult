# Copyright 2013 The Chromium Authors. All rights reserved.
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

from tvcm import strip_js_comments


class DepsException(Exception):
  """Exceptions related to module dependency resolution."""
  pass


class Module(object):
  """Represents a javascript module.

  It can either be directly requested, e.g. passed in by name to
  calc_load_sequence, or created by being referenced a module via the
  base.require directive.

  Interesting properties include:
    name: Module name, may include a namespace, e.g. 'ui.foo'.
    filename: The filename of the actual module.
    contents: The text contents of the module
    dependent_modules: Other modules that this module depends on.

  In addition to these properties, a Module also contains lists of other
  resources that it depends on.
  """
  def __init__(self, name=None):
    self.name = name
    self.filename = None
    self.contents = None

    self.dependent_module_names = []
    self.dependent_modules = []

    self.dependent_raw_script_relative_paths = []
    self.dependent_raw_scripts = []
    self.style_sheet_names = []
    self.style_sheets = []
    self.html_template_names = []
    self.html_templates = []

  def __repr__(self):
    return 'Module(%s)' % self.name

  @staticmethod
  def relative_filename_to_module_name(relative_path):
    dirname = os.path.dirname(relative_path)
    modname  = os.path.splitext(os.path.basename(relative_path))[0]
    if len(dirname):
      name = dirname.replace(os.path.sep, '.') + '.' + modname
    else:
      name = modname
    return name

  @staticmethod
  def html_contents_is_polymer_module(contents):
    return '<polymer-component>' in contents

  def load_and_parse(self, module_filename,
                     module_contents=None):
    """Load a module's contents and read the base.require statements.

    Args:
      module_filename: The path to the module file.
      module_contents: If specified, this is used and the file isn't read.

    Raises:
      IOError: There is some error reading the module's contents.
    """
    if not module_contents:
      f = open(module_filename, 'r')
      self.contents = f.read()
      f.close()
    else:
      self.contents = module_contents
    self.filename = module_filename
    if self.filename.endswith('html'):
      # ... parse_as_html() using parse_html_deps.py
      raise NotImplementedError()
    else:
      stripped_text = strip_js_comments.strip_js_comments(self.contents)
      self._validate_uses_strict_mode(stripped_text)
      self._parse_definition(stripped_text)

  def register(self, loader):
    assert self.name not in loader.loaded_scripts
    loader.loaded_scripts[self.name] = self

  def resolve(self, loader):
    """Populates the lists of resources that this module depends on.

    Args:
      loader: An instance of ResourceLoader.

    Raises:
      DepsException: There was a problem finding one of the dependencies.
      Exception: There was a problem parsing a module that this one depends on.
    """
    assert self.name, 'Module name must be set before dep resolution.'
    assert self.filename, 'Module filename must be set before dep resolution.'
    assert self.name in loader.loaded_scripts, 'Module must be registered in resource loader before resolution'

    # Load modules that this module depends on.
    for name in self.dependent_module_names:
      # If a module with this name has already been resolved, skip it.
      if name in loader.loaded_scripts:
        assert loader.loaded_scripts[name].contents
        self.dependent_modules.append(loader.loaded_scripts[name])
        continue

      filename, contents = loader.find_and_load_module(name)
      if not filename:
        raise DepsException('No file for module %(name)s needed by %(dep)s' %
          {'name': name, 'dep': self.filename})

      module = Module(name)
      module.register(loader)
      self.dependent_modules.append(module)
      try:
        module.load_and_parse(filename, contents)
      except Exception, e:
        raise Exception('While processing ' + filename + ': ' + e.message)
      module.resolve(loader)

    for relative_raw_script_path in self.dependent_raw_script_relative_paths:
      filename, contents = loader.find_and_load_raw_script(relative_raw_script_path)
      if not filename:
        raise DepsException('Could not find a file for raw script %s' % relative_raw_script_path)

      if filename in loader.loaded_raw_scripts:
        assert loader.loaded_raw_scripts[filename].contents
        self.dependent_raw_scripts.append(loader.loaded_raw_scripts[filename])
        continue

      raw_script = RawScript(filename, contents)
      raw_script.register(loader)
      self.dependent_raw_scripts.append(raw_script)

    for name in self.style_sheet_names:
      if name in loader.loaded_style_sheets:
        assert loader.loaded_style_sheets[name].contents
        self.style_sheets.append(loader.loaded_style_sheets[name])
        continue

      filename, contents = loader.find_and_load_style_sheet(name)
      if not filename:
        raise DepsException('Could not find a file for stylesheet %s' % name)

      style_sheet = StyleSheet(name, filename, contents)
      loader.loaded_style_sheets[name] = style_sheet
      self.style_sheets.append(style_sheet)

    for name in self.html_template_names:
      if name in loader.loaded_html_templates:
        assert loader.loaded_html_templates[name].contents
        self.html_templates.append(loader.loaded_html_templates[name])
        continue

      filename, contents = loader.find_and_load_html_template(name)
      if not filename:
        raise DepsException(
            'Could not find a file for html template named %s' % name)

      html_template = HTMLTemplate(name, filename, contents)
      loader.loaded_html_templates[name] = html_template
      self.html_templates.append(html_template)

  def compute_load_sequence_recursive(self, load_sequence, already_loaded_set,
                                      depth=0):
    """Recursively builds up a load sequence list.

    Args:
      load_sequence: A list which will be incrementally built up.
      already_loaded_set: A set of modules that has already been added to the
          load sequence list.
      depth: The depth of recursion. If it too deep, that indicates a loop.
    """
    if depth > 32:
      raise Exception('Include loop detected on %s', self.name)
    for dependent_module in self.dependent_modules:
      dependent_module.compute_load_sequence_recursive(
          load_sequence, already_loaded_set, depth+1)
    if self.name not in already_loaded_set:
      already_loaded_set.add(self.name)
      load_sequence.append(self)

  def _validate_uses_strict_mode(self, stripped_text):
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
      raise DepsException('%s must use strict mode' % self.name)

  def _parse_definition(self, stripped_text):
    """Parses the base.require* lines in the module and populates the lists
    of resource names.

    Args:
      stripped_text: Javascript source code with comments stripped out.

    Raises:
      DepsException: The name of a resource was not formatted properly.
    """
    if not self.name:
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
          raise DepsException('Slashes are not allowed in module names. '
                              "Use '.' instead: %s" % dependent_module_name)
        if dependent_module_name.endswith('js'):
          raise DepsException("module names shouldn't end with .js"
                              'The module system will append that for you: %s' %
                              dependent_module_name)
        self.dependent_module_names.append(dependent_module_name)
      elif m == m_s:
        style_sheet_name = m.group(2)
        if '/' in style_sheet_name:
          raise DepsException('Slashes are not allowed in style sheet names. '
                              "Use '.' instead: %s" % style_sheet_name)
        if style_sheet_name.endswith('.css'):
          raise DepsException('Style sheets should not end in .css. '
                              'The module system will append that for you: %s' %
                              style_sheet_name)
        self.style_sheet_names.append(style_sheet_name)
      elif m == m_t:
        html_template_name = m.group(2)
        if '/' in html_template_name:
          raise DepsException('Slashes are not allowed in html template names. '
                              "Use '.' instead: %s" % html_template_name)
        if html_template_name.endswith('.html'):
          raise DepsException(
              'HTML templates resource names should not include extension. '
              'The module system will append that for you.' %
              html_template_name)
        self.html_template_names.append(html_template_name)
      elif m == m_irs:
        name = m.group(2)
        self.dependent_raw_script_relative_paths.append(name)

      rest = rest[m.end():]


class StyleSheet(object):
  """Represents a stylesheet resource referenced by a module via the
  base.requireStylesheet(xxx) directive."""
  def __init__(self, name, filename, contents):
    self.name = name
    self.filename = filename
    self.contents = contents

  def __repr__(self):
    return "StyleSheet(%s)" % self.name


class HTMLTemplate(object):
  """Represents an html template resource referenced by a module via the
  base.requireTemplate(xxx) directive."""
  def __init__(self, name, filename, contents):
    self.name = name
    self.filename = filename
    self.contents = contents

  def __repr__(self):
    return "HTMLTemplate(%s)" % self.name


class RawScript(object):
  """Represents a raw script resource referenced by a module via the
  base.requireRawScript(xxx) directive."""
  def __init__(self, filename, contents):
    self.filename = filename
    self.contents = contents

  def register(self, loader):
    assert self.filename not in loader.loaded_raw_scripts
    loader.loaded_raw_scripts[self.filename] = self

  def __repr__(self):
    return "RawScript(%s)" % self.filename
