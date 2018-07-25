# Copyright 2018 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import string

from dashboard.common import namespaced_stored_object


_BOT_CONFIGURATIONS = 'bot_configurations'


def Get(name):
  configurations = namespaced_stored_object.Get(_BOT_CONFIGURATIONS)
  configuration = configurations[name]
  if 'alias' in configuration:
    return configurations[configuration['alias']]
  return configuration


def List():
  bot_configurations = namespaced_stored_object.Get(_BOT_CONFIGURATIONS)
  canonical_names = [name for name, value in bot_configurations.iteritems()
                     if 'alias' not in value]
  return sorted(canonical_names, key=string.lower)
