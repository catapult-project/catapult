# Copyright 2014 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.
import base64
import os
import re

class Image(object):
  def __init__(self, resource):
    self.resource = resource
    self.aliases = []

  @property
  def relative_path(self):
    return self.resource.relative_path

  @property
  def absolute_path(self):
    return self.resource.absolute_path

  @property
  def contents(self):
    return self.resource.contents

class StyleSheet(object):
  """Represents a stylesheet resource referenced by a module via the
  base.requireStylesheet(xxx) directive."""
  def __init__(self, loader, name, resource):
    self.loader = loader
    self.name = name
    self.resource = resource
    self._images = None

  @property
  def filename(self):
    return self.resource.absolute_path

  @property
  def contents(self):
    return self.resource.contents

  def __repr__(self):
    return "StyleSheet(%s)" % self.name

  @property
  def images(self):
    if self._images != None:
      return self._images
    self.load()
    return self._images

  @property
  def contents_with_inlined_images(self):
    images_by_url = {}
    for i in self.images:
      for a in i.aliases:
        images_by_url[a] = i

    def InlineUrl(m):
      url = m.group('url')
      image = images_by_url[url]

      ext = os.path.splitext(image.absolute_path)[1]
      data = base64.standard_b64encode(image.contents)

      return "url(data:image/%s;base64,%s)" % (ext[1:], data)

    # I'm assuming we only have url()'s associated with images
    return re.sub('url\((?P<quote>"|\'|)(?P<url>[^"\'()]*)(?P=quote)\)',
                  lambda m: InlineUrl(m),
                  self.contents)


  def load(self):
    matches = re.findall(
      'url\((?:["|\']?)([^"\'()]*)(?:["|\']?)\)',
      self.contents)

    module_dirname = os.path.dirname(self.resource.absolute_path)
    def resolve_url(url):
      if os.path.isabs(url):
        raise module.DepsException('URL references must be relative')
      # URLS are relative to this module's directory
      abs_path = os.path.abspath(os.path.join(module_dirname, url))
      image = self.loader.load_image(abs_path)
      image.aliases.append(url)
      return image

    self._images = [resolve_url(x) for x in matches]
