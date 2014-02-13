// Copyright (c) 2013 The Chromium Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

'use strict';

tvcm.require('tracing.timeline_display_transform');
tvcm.require('tracing.timeline_display_transform_animations');
tvcm.require('tvcm.ui.animation_controller');

tvcm.unittest.testSuite('tracing.timeline_display_transform_animations_test', function() { // @suppress longLineCheck
  var TimelineDisplayTransform = tracing.TimelineDisplayTransform;
  var TimelineDisplayTransformPanAnimation =
      tracing.TimelineDisplayTransformPanAnimation;
  var TimelineDisplayTransformZoomToAnimation =
      tracing.TimelineDisplayTransformZoomToAnimation;

  test('panBasic', function() {
    var target = new TimelineDisplayTransform();
    target.cloneAnimationState = function() {
      return this.clone();
    };

    var a = new TimelineDisplayTransformPanAnimation(10, 0, 100);

    var controller = new tvcm.ui.AnimationController();
    controller.target = target;
    controller.queueAnimation(a, 0);

    tvcm.forcePendingRAFTasksToRun(50);
    assertTrue(target.panX > 0);
    tvcm.forcePendingRAFTasksToRun(100);
    assertFalse(controller.hasActiveAnimation);
    assertEquals(10, target.panX);
  });

  test('panTakeover', function() {
    var target = new TimelineDisplayTransform();
    target.cloneAnimationState = function() {
      return this.clone();
    };

    var b = new TimelineDisplayTransformPanAnimation(10, 0, 100);
    var a = new TimelineDisplayTransformPanAnimation(10, 0, 100);

    var controller = new tvcm.ui.AnimationController();
    controller.target = target;
    controller.queueAnimation(a, 0);

    tvcm.forcePendingRAFTasksToRun(50);
    controller.queueAnimation(b, 50);

    tvcm.forcePendingRAFTasksToRun(100);
    assertTrue(controller.hasActiveAnimation);

    tvcm.forcePendingRAFTasksToRun(150);
    assertFalse(controller.hasActiveAnimation);
    assertEquals(20, target.panX);
  });

});
