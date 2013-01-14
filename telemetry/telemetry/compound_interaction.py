# Copyright (c) 2012 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.
from telemetry import page_interaction

class CompoundInteraction(page_interaction.PageInteraction):
  def __init__(self, attributes=None):
    super(CompoundInteraction, self).__init__(attributes)
    self._interaction_list = []
    from telemetry import all_page_interactions
    for interaction_data in self.actions:
      interaction = all_page_interactions.FindClassWithName(
          interaction_data['action'])(interaction_data)
      self._interaction_list.append(interaction)

  def CustomizeBrowserOptions(self, options):
    for interaction in self._interaction_list:
      interaction.CustomizeBrowserOptions(options)

  def RunInteraction(self, page, tab):
    for interaction in self._interaction_list:
      interaction.WillRunInteraction(page, tab)
      interaction.RunInteraction(page, tab)
