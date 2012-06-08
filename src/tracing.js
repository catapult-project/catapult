// Copyright (c) 2012 The Chromium Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

// NOTE: this file is meant to be used by chrome's about:tracing build system.
// These <includes> get flattened into the main system as part of the build
// process.
<include src="base.js">
<include src="event_target.js">
<include src="ui.js">
<include src="focus_outline_manager.js">
<include src="overlay.js">
<include src="tracing_controller.js">
<include src="timeline_model.js">
<include src="linux_perf_importer.js">
<include src="trace_event_importer.js">
<include src="sorted_array_utils.js">
<include src="measuring_stick.js">
<include src="timeline.js">
<include src="timeline_analysis.js">
<include src="timeline_track.js">
<include src="fast_rect_renderer.js">
<include src="profiling_view.js">
<include src="timeline_view.js">

var tracingController;
var profilingView;  // Made global for debugging purposes only.

/**
 * Main entry point called once the page has loaded.
 */
document.addEventListener('DOMContentLoaded', function() {
  tracingController = new tracing.TracingController();

  profilingView = document.body.querySelector('#profiling-view');
  base.ui.decorate(profilingView, tracing.ProfilingView);
  profilingView.tracingController = tracingController;
});