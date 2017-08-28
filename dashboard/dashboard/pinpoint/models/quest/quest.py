# Copyright 2016 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.


class Quest(object):
  """A description of work to do on a Change.

  Examples include building a binary or running a test. The concept is borrowed
  from Dungeon Master (go/dungeon-master). In Dungeon Master, Quests can depend
  on other Quests, but we're not that fancy here. So instead of having one big
  Quest that depends on smaller Quests, we just run all the small Quests
  linearly. (E.g. build, then test, then read test results). We'd like to
  replace this model with Dungeon Master entirely, when it's ready.

  A Quest has a Start method, which takes as parameters the result_arguments
  from the previous Quest's Execution.
  """

  def __str__(self):
    raise NotImplementedError()
