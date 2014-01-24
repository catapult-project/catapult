# Copyright 2013 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.
"""ResourceFinder is a helper class for finding resources given their name."""

import os
from tvcm import module
from tvcm import js_module

class Resource(object):
  """Represents a file found via a path search."""
  def __init__(self, toplevel_dir, absolute_path):
    self.toplevel_dir = toplevel_dir
    self.absolute_path = absolute_path
    self._contents = None

  @property
  def relative_path(self):
    """The path to the file from the top-level directory"""
    return os.path.relpath(self.absolute_path, self.toplevel_dir)

  @property
  def name(self):
    """The dotted name for this resource based on its relative path."""
    return self.name_from_relative_path(self.relative_path)

  @staticmethod
  def name_from_relative_path(relative_path):
    dirname = os.path.dirname(relative_path)
    modname  = os.path.splitext(os.path.basename(relative_path))[0]
    if len(dirname):
      name = dirname.replace(os.path.sep, '.') + '.' + modname
    else:
      name = modname
    return name

  @property
  def contents(self):
    if self._contents:
      return self._contents
    if not os.path.exists(self.absolute_path):
      raise Exception('%s not found.' % self.absolute_path)
    f = open(self.absolute_path, 'r')
    self._contents = f.read()
    f.close()
    return self._contents


class ResourceLoader(object):
  """Manges loading modules and their dependencies from files.

  Modules handle parsing and the construction of their individual dependency
  pointers. The loader deals with bookkeeping of what has been loaded, and
  mapping names to file resources.

  """
  def __init__(self, search_paths, data_paths):
    assert isinstance(search_paths, list)
    self._search_paths = [os.path.abspath(path) for path in search_paths]
    self._data_paths = [os.path.abspath(path) for path in data_paths]
    self.loaded_scripts = {}
    self.loaded_raw_scripts = {}
    self.loaded_style_sheets = {}
    self.loaded_html_templates = {}

  @property
  def search_paths(self):
    """A list of base directories to search for modules under."""
    return self._search_paths

  def find_resource(self, some_path):
    """Finds a Resource for the given path.

    Args:
      some_path: A relative or absolute path to a file.

    Returns:
      A Resource or None.
    """
    if os.path.isabs(some_path):
      return self.find_resource_given_absolute_path(some_path)
    else:
      return self.find_resource_given_relative_path(some_path)

  def find_resource_given_absolute_path(self, absolute_path):
    """Returns a Resource for the given absolute path."""
    for search_path in self._search_paths:
      if absolute_path.startswith(search_path):
        return Resource(search_path, absolute_path)
    return None

  def find_resource_given_relative_path(self, relative_path):
    """Returns a Resource for the given relative path."""
    absolute_path = None
    for search_path in self._search_paths:
      absolute_path = os.path.join(search_path, relative_path)
      if os.path.exists(absolute_path):
        return Resource(search_path, absolute_path)
    return None


  def _find_resource_given_name_and_suffix(self, requested_name, extension, return_resource=False):
    """Searches for a file and reads its contents.

    Args:
      requested_name: The name of the resource that was requested.
      extension: The extension for this requested resource.

    Returns:
      A (path, contents) pair.
    """
    pathy_name = requested_name.replace('.', os.sep)
    filename = pathy_name + extension

    resource = self.find_resource_given_relative_path(filename)
    if return_resource:
      return resource
    if not resource:
      return None, None
    return _read_file(resource.absolute_path)

  def _find_module_resource(self, requested_module_name):
    """Finds a module javascript file and returns a Resource, or none."""
    js_resource = self._find_resource_given_name_and_suffix(requested_module_name, '.js', return_resource=True)
    html_resource = self._find_resource_given_name_and_suffix(requested_module_name, '.html', return_resource=True)
    if js_resource and html_resource:
      if module.Module.html_contents_is_polymer_module(html_resource.contents):
        return html_resource
      return js_resource
    elif js_resource:
      return js_resource
    return html_resource

  def load_module(self, module_name=None, module_filename=None, context=None):
    assert bool(module_name) ^ bool(module_filename), 'Must provide module_name or module_filename.'
    if module_filename:
      resource = self.find_resource(module_filename)
      if not resource:
        raise Exception('Could not find %s in %s' % (
            filename, repr(self.search_paths)))
      module_name = resource.name
    else:
      resource = None # Will be set if we end up needing to load.

    if module_name in self.loaded_scripts:
      assert self.loaded_scripts[module_name].contents
      return self.loaded_scripts[module_name]

    if not resource: # happens when module_name was given
      resource = self._find_module_resource(module_name)
      if not resource:
        if context:
          raise module.DepsException('No resource for module %(module_name)s needed by %(context)' %
                                     {'module_name': module_name, 'context': context})
        else:
          raise module.DepsException('No resource for module %s' % module_name)

    m = js_module.JSModule(self, module_name, resource.absolute_path)
    m.parse()
    self.loaded_scripts[module_name] = m
    m.load()
    return m

  def load_raw_script(self, relative_raw_script_path):
    resource = None
    for data_path in self._data_paths:
      possible_absolute_path = os.path.join(data_path, relative_raw_script_path)
      if os.path.exists(possible_absolute_path):
        resource = Resource(data_path, possible_absolute_path)
        break
    if not resource:
      raise DepsException('Could not find a file for raw script %s in %s' % (
        relative_raw_script_path, self._data_paths))

    if resource.absolute_path in self.loaded_raw_scripts:
      return self.loaded_raw_scripts[resource.absolute_path]

    raw_script = module.RawScript(resource.absolute_path, resource.contents)
    self.loaded_raw_scripts[resource.absolute_path] = raw_script
    return raw_script

  def load_style_sheet(self, name):
    if name in self.loaded_style_sheets:
      return self.loaded_style_sheets[name]

    resource = self._find_resource_given_name_and_suffix(name, '.css', return_resource=True)
    if not resource:
      raise DepsException('Could not find a file for stylesheet %s' % name)

    style_sheet = module.StyleSheet(name, resource.absolute_path, resource.contents)
    self.loaded_style_sheets[name] = style_sheet
    return style_sheet

  def load_html_template(self, name):
    if name in self.loaded_html_templates:
      return self.loaded_html_templates[name]

    resource = self._find_resource_given_name_and_suffix(name, '.html', return_resource=True)
    if not resource:
      raise DepsException(
          'Could not find a file for html template named %s' % name)

    html_template = module.HTMLTemplate(name, resource.absolute_path, resource.contents)
    self.loaded_html_templates[name] = html_template
    return html_template

def _read_file(absolute_path):
  """Reads a file and returns a (path, contents) pair.

  Args:
    absolute_path: Absolute path to a file.

  Raises:
    Exception: The given file doesn't exist.
    IOError: There was a problem opening or reading the file.
  """
  if not os.path.exists(absolute_path):
    raise Exception('%s not found.' % absolute_path)
  f = open(absolute_path, 'r')
  contents = f.read()
  f.close()
  return absolute_path, contents
