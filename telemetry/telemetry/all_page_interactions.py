# Copyright (c) 2012 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.
import os

from telemetry import discover
from telemetry import page_interaction

_page_interaction_classes = discover.Discover(os.path.dirname(__file__),
                                              'interaction',
                                              page_interaction.PageInteraction,
                                              import_error_should_raise=True)

def GetAllClasses():
  return list(_page_interaction_classes.values())

def FindClassWithName(name):
  return _page_interaction_classes.get(name)

def RegisterClassForTest(name, clazz):
  _page_interaction_classes[name] = clazz
