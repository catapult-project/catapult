# Copyright (c) 2012 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

from telemetry import all_page_interactions
from telemetry import compound_interaction
from telemetry import page_interaction
from telemetry import tab_test_case

class CompoundInteractionTest(tab_test_case.TabTestCase):
  interaction1_called = False
  interaction2_called = False

  def __init__(self, *args):
    super(CompoundInteractionTest, self).__init__(*args)

  def testCompoundInteraction(self):

    class MockInteraction1(page_interaction.PageInteraction):
      def RunInteraction(self, page, tab):
        CompoundInteractionTest.interaction1_called = True

    class MockInteraction2(page_interaction.PageInteraction):
      def RunInteraction(self, page, tab):
        CompoundInteractionTest.interaction2_called = True

    all_page_interactions.RegisterClassForTest('mock1', MockInteraction1)
    all_page_interactions.RegisterClassForTest('mock2', MockInteraction2)

    i = compound_interaction.CompoundInteraction({
        'action': 'compound',
        'actions': [
            {
                'action': 'mock1'
            },
            {
                'action': 'mock2'
            }
        ]
    })
    i.RunInteraction({}, self._tab)
    self.assertTrue(CompoundInteractionTest.interaction1_called)
    self.assertTrue(CompoundInteractionTest.interaction2_called)
