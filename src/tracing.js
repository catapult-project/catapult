// Copyright (c) 2012 The Chromium Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

<include src="gpu_internals/browser_bridge.js">
<include src="tracing/overlay.js">
<include src="tracing/tracing_controller.js">
<include src="tracing/timeline_model.js">
<include src="tracing/linux_perf_importer.js">
<include src="tracing/trace_event_importer.js">
<include src="tracing/sorted_array_utils.js">
<include src="tracing/measuring_stick.js">
<include src="tracing/timeline.js">
<include src="tracing/timeline_analysis.js">
<include src="tracing/timeline_track.js">
<include src="tracing/fast_rect_renderer.js">
<include src="tracing/profiling_view.js">
<include src="tracing/timeline_view.js">

var browserBridge;
var tracingController;
var profilingView;  // Made global for debugging purposes only.

/**
 * Main entry point called once the page has loaded.
 */
function onLoad() {
  browserBridge = new gpu.BrowserBridge();
  tracingController = new tracing.TracingController();

  profilingView = $('profiling-view');
  cr.ui.decorate(profilingView, tracing.ProfilingView);
  profilingView.tracingController = tracingController;
}

document.addEventListener('DOMContentLoaded', onLoad);
