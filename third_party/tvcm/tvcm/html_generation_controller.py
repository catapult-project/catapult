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
from tvcm import style_sheet


class HTMLGenerationController(object):
  def __init__(self):
    self.current_module = None

  def GetHTMLForStylesheetHRef(self, href):
    return None

  def GetHTMLForInlineStylesheet(self, contents):
    if self.current_module == None:
      if re.search('url\(.+\)', contents):
        raise Exception('Default HTMLGenerationController cannot handle inline style urls')
      return contents

    module_dirname = os.path.dirname(self.current_module.resource.absolute_path)
    ss = style_sheet.ParsedStyleSheet(
        self.current_module.loader, module_dirname, contents)
    return ss.contents_with_inlined_images
