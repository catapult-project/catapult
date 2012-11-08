# Copyright (c) 2012 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.
from telemetry import page_interaction

class CompoundInteraction(page_interaction.PageInteraction):
  def __init__(self, attributes=None):
    super(CompoundInteraction, self).__init__(attributes)

  def PerformInteraction(self, page, tab):
    for interaction_data in self.actions:
      interaction = page_interaction.FindClassWithName(
          interaction_data['action'])(interaction_data)
      interaction.PerformInteraction(page, tab)


page_interaction.RegisterClass('compound', CompoundInteraction)
