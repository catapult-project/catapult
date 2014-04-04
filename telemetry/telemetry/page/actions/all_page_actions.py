# Copyright (c) 2012 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.
import os

from telemetry.core import discover
from telemetry.core import util
from telemetry.page.actions import page_action

# pylint: disable=W0611
# TODO(nednguyen): Remove all of these imports when we done porting all actions
# to action_runner
from telemetry.page.actions.interact import InteractAction
from telemetry.page.actions.javascript import JavascriptAction
from telemetry.page.actions.javascript_click import ClickElementAction
from telemetry.page.actions.js_collect_garbage import JsCollectGarbageAction
from telemetry.page.actions.loop import LoopAction
from telemetry.page.actions.media_action import MediaAction
from telemetry.page.actions.navigate import NavigateAction
from telemetry.page.actions.pinch import PinchAction
from telemetry.page.actions.play import PlayAction
from telemetry.page.actions.reload import ReloadAction
from telemetry.page.actions.scroll import ScrollAction
from telemetry.page.actions.seek import SeekAction
from telemetry.page.actions.tap import TapAction
from telemetry.page.actions.swipe import SwipeAction
from telemetry.page.actions.wait import WaitAction


_page_action_classes = discover.DiscoverClasses(
    os.path.dirname(__file__), util.GetTelemetryDir(), page_action.PageAction)

def GetAllClasses():
  return list(_page_action_classes.values())

def FindClassWithName(name):
  return _page_action_classes.get(name)

def RegisterClassForTest(name, clazz):
  _page_action_classes[name] = clazz
