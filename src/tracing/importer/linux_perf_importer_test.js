// Copyright (c) 2013 The Chromium Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

'use strict';

base.require('tracing.test_utils');
base.require('tracing.importer.linux_perf_importer');

base.unittest.testSuite('tracing.importer.linux_perf_importer', function() {
  test('lineParserWithLegacyFmt', function() {
    var p = tracing.importer._LinuxPerfImporterTestExports.lineParserWithLegacyFmt; // @suppress longLineCheck
    var x = p('   <idle>-0     [001]  4467.843475: sched_switch: ' +
        'prev_comm=swapper prev_pid=0 prev_prio=120 prev_state=R ==> ' +
        'next_comm=SurfaceFlinger next_pid=178 next_prio=112');
    assertNotNull(x);
    assertEquals('<idle>', x.threadName);
    assertEquals('0', x.pid);
    assertEquals('001', x.cpuNumber);
    assertEquals('4467.843475', x.timestamp);
    assertEquals('sched_switch', x.eventName);
    assertEquals('prev_comm=swapper prev_pid=0 prev_prio=120 prev_state=R' +
        ' ==> next_comm=SurfaceFlinger next_pid=178 next_prio=112', x.details);

    var x = p('Binder-Thread #-647   [001]   260.464294: sched_switch: ' +
        'prev_comm=Binder Thread # prev_pid=647 prev_prio=120 prev_state=D ' +
        ' ==> next_comm=.android.chrome next_pid=1562 next_prio=120');
    assertNotNull(x);
    assertEquals('Binder-Thread #', x.threadName);
    assertEquals('647', x.pid);
  });

  test('lineParserWithIRQInfo', function() {
    var p = tracing.importer._LinuxPerfImporterTestExports.lineParserWithIRQInfo; // @suppress longLineCheck
    var x = p('     systrace.sh-5441  [001] d...  1031.091570: ' +
        'sched_wakeup: comm=debugd pid=4978 prio=120 success=1 target_cpu=000');
    assertNotNull(x);
    assertEquals('systrace.sh', x.threadName);
    assertEquals('5441', x.pid);
    assertEquals('001', x.cpuNumber);
    assertEquals('1031.091570', x.timestamp);
    assertEquals('sched_wakeup', x.eventName);
    assertEquals('comm=debugd pid=4978 prio=120 success=1 target_cpu=000', x.details); // @suppress longLineCheck
  });

  test('lineParserWithTGID', function() {
    var p = tracing.importer._LinuxPerfImporterTestExports.lineParserWithTGID;
    var x = p('     systrace.sh-5441  (54321) [001] d...  1031.091570: ' +
        'sched_wakeup: comm=debugd pid=4978 prio=120 success=1 target_cpu=000');
    assertNotNull(x);
    assertEquals('systrace.sh', x.threadName);
    assertEquals('5441', x.pid);
    assertEquals('54321', x.tgid);
    assertEquals('001', x.cpuNumber);
    assertEquals('1031.091570', x.timestamp);
    assertEquals('sched_wakeup', x.eventName);
    assertEquals('comm=debugd pid=4978 prio=120 success=1 target_cpu=000', x.details); // @suppress longLineCheck

    var x = p('     systrace.sh-5441  (  321) [001] d...  1031.091570: ' +
        'sched_wakeup: comm=debugd pid=4978 prio=120 success=1 target_cpu=000');
    assertNotNull(x);
    assertEquals('321', x.tgid);

    var x = p('     systrace.sh-5441  (-----) [001] d...  1031.091570: ' +
        'sched_wakeup: comm=debugd pid=4978 prio=120 success=1 target_cpu=000');
    assertNotNull(x);
    assertEquals(undefined, x.tgid);
  });

  test('autodetectLineCornerCases', function() {
    var detectParser =
        tracing.importer._LinuxPerfImporterTestExports.autoDetectLineParser;
    var lineParserWithLegacyFmt =
        tracing.importer._LinuxPerfImporterTestExports.lineParserWithLegacyFmt;
    var lineParserWithIRQInfo =
        tracing.importer._LinuxPerfImporterTestExports.lineParserWithIRQInfo;
    var lineParserWithTGID =
        tracing.importer._LinuxPerfImporterTestExports.lineParserWithTGID;

    var lineWithLegacyFmt =
        'systrace.sh-8170  [001] 15180.978813: sched_switch: ' +
        'prev_comm=systrace.sh prev_pid=8170 prev_prio=120 ' +
        'prev_state=x ==> next_comm=kworker/1:0 next_pid=7873 ' +
        'next_prio=120';
    var detected = detectParser(lineWithLegacyFmt);
    assertEquals(detected, lineParserWithLegacyFmt);

    var lineWithIRQInfo =
        'systrace.sh-8170  [001] d... 15180.978813: sched_switch: ' +
        'prev_comm=systrace.sh prev_pid=8170 prev_prio=120 ' +
        'prev_state=x ==> next_comm=kworker/1:0 next_pid=7873 ' +
        'next_prio=120';
    var detected = detectParser(lineWithIRQInfo);
    assertEquals(detected, lineParserWithIRQInfo);

    var lineWithTGID =
        'systrace.sh-8170  (54321) [001] d... 15180.978813: sched_switch: ' +
        'prev_comm=systrace.sh prev_pid=8170 prev_prio=120 ' +
        'prev_state=x ==> next_comm=kworker/1:0 next_pid=7873 ' +
        'next_prio=120';
    var detected = detectParser(lineWithTGID);
    assertEquals(detected, lineParserWithTGID);
  });

  test('traceEventClockSyncRE', function() {
    var re = tracing.importer._LinuxPerfImporterTestExports.traceEventClockSyncRE; // @suppress longLineCheck
    var x = re.exec('trace_event_clock_sync: parent_ts=19581477508');
    assertNotNull(x);
    assertEquals('19581477508', x[1]);

    var x = re.exec('trace_event_clock_sync: parent_ts=123.456');
    assertNotNull(x);
    assertEquals('123.456', x[1]);
  });

  test('canImport', function() {
    var lines = [
      '# tracer: nop',
      '#',
      '#           TASK-PID    CPU#    TIMESTAMP  FUNCTION',
      '#              | |       |          |         |',
      '          <idle>-0     [001]  4467.843475: sched_switch: ' +
          'prev_comm=swapper prev_pid=0 prev_prio=120 prev_state=R ==> ' +
          'next_comm=SurfaceFlinger next_pid=178 next_prio=112',

      '  SurfaceFlinger-178   [001]  4467.843536: sched_switch: ' +
          'prev_comm=SurfaceFlinger prev_pid=178 prev_prio=112 prev_state=S ' +
          '==> next_comm=kworker/u:2 next_pid=2844 next_prio=120',

      '     kworker/u:2-2844  [001]  4467.843567: sched_switch: ' +
          'prev_comm=kworker/u:2 prev_pid=2844 prev_prio=120 prev_state=S ' +
          '==> next_comm=swapper next_pid=0 next_prio=120',

      '          <idle>-0     [001]  4467.844208: sched_switch: ' +
          'prev_comm=swapper prev_pid=0 prev_prio=120 prev_state=R ==> ' +
          'next_comm=kworker/u:2 next_pid=2844 next_prio=120'
    ];
    assertTrue(tracing.importer.LinuxPerfImporter.canImport(lines.join('\n')));

    var lines = [
      '          <idle>-0     [001]  4467.843475: sched_switch: ' +
          'prev_comm=swapper prev_pid=0 prev_prio=120 prev_state=R ==> ' +
              'next_comm=SurfaceFlinger next_pid=178 next_prio=112'
    ];
    assertTrue(tracing.importer.LinuxPerfImporter.canImport(lines.join('\n')));

    var lines = [
      '          <idle>-0     [001]  4467.843475: sched_switch: ' +
          'prev_comm=swapper prev_pid=0 prev_prio=120 prev_state=R ==> ' +
          'next_comm=SurfaceFlinger next_pid=178 next_prio=112',

      '  SurfaceFlinger-178   [001]  4467.843536: sched_switch: ' +
          'prev_comm=SurfaceFlinger prev_pid=178 prev_prio=112 ' +
          'prev_state=S ==> next_comm=kworker/u:2 next_pid=2844 ' +
          'next_prio=120'
    ];
    assertTrue(tracing.importer.LinuxPerfImporter.canImport(lines.join('\n')));

    var lines = [
      'SomeRandomText',
      'More random text'
    ];
    assertFalse(tracing.importer.LinuxPerfImporter.canImport(lines.join('\n')));
  });

  test('canImport34AndLater', function() {
    var lines = [
      '# tracer: nop',
      '#',
      '# entries-in-buffer/entries-written: 55191/55191   #P:2',
      '#',
      '#                              _-----=> irqs-off',
      '#                             / _----=> need-resched',
      '#                            | / _---=> hardirq/softirq',
      '#                            || / _--=> preempt-depth',
      '#                            ||| /     delay',
      '#           TASK-PID   CPU#  ||||    TIMESTAMP  FUNCTION',
      '#              | |       |   ||||       |         |',
      '     systrace.sh-5441  [001] d...  1031.091570: sched_wakeup: ' +
          'comm=debugd pid=4978 prio=120 success=1 target_cpu=000',
      '     systrace.sh-5441  [001] d...  1031.091584: sched_switch: ' +
          'prev_comm=systrace.sh prev_pid=5441 prev_prio=120 prev_state=x ' +
          '==> next_comm=chrome next_pid=5418 next_prio=120'
    ];
    assertTrue(tracing.importer.LinuxPerfImporter.canImport(lines.join('\n')));

    var lines = [
      '     systrace.sh-5441  [001] d...  1031.091570: sched_wakeup: ' +
          'comm=debugd pid=4978 prio=120 success=1 target_cpu=000',
      '     systrace.sh-5441  [001] d...  1031.091584: sched_switch: ' +
          'prev_comm=systrace.sh prev_pid=5441 prev_prio=120 prev_state=x ' +
          '==> next_comm=chrome next_pid=5418 next_prio=120'
    ];
    assertTrue(tracing.importer.LinuxPerfImporter.canImport(lines.join('\n')));
  });

  test('canImportSystraceFile', function() {
    var html_lines = [
      '<!DOCTYPE HTML>',
      '<html>',
      '<head i18n-values="dir:textdirection;">',
      '<title>Android System Trace</title>',
      '<style type="text/css">tabbox{-webkit-box-orient:vertical;display:-webkit-box;}tabs{-webkit-padding-start</style>', // @suppress longLineCheck
      '<script language="javascript">function onLoad(){reload()}function reload(){if(linuxPerfData){var g=new tracing.TraceModel;g.importEvents("[]",!0,[linuxPerfData]);var e=document.querySelector(".view");cr.ui.decorate(e,tracing.View);e.model=g;e.tabIndex=1;e.timeline.focusElement=e}}document.addEventListener("DOMContentLoaded",onLoad);var global=this;', // @suppress longLineCheck
      'this.cr=function(){function g(a,b,c,f){var e=new cr.Event(b+"Change");e.propertyName=b;e.newValue=c;e.oldValue=f;a.dispatchEvent(e)}function e(a){return a.replace(/([A-Z])/g,"-$1").toLowerCase()}function c(b,c){switch(c){case a.JS:var f=b+"_";return function(){return this[f]};case a.ATTR:var h=e(b);return function(){return this.getAttribute(h)};case a.BOOL_ATTR:return h=e(b),function(){return this.hasAttribute(h)}}}function f(b,c,f){switch(c){case a.JS:var h=b+"_";return function(a){var c=this[h];', // @suppress longLineCheck
      '  </div>',
      '  <script>',
      '  var linuxPerfData = "\\',
      '# tracer: nop\\n\\',
      '#\\n\\',
      '#           TASK-PID    CPU#    TIMESTAMP  FUNCTION\\n\\',
      '#              | |       |          |         |\\n\\',
      '          atrace-14662 [000] 50260.647576: sched_switch: prev_comm=atrace prev_pid=14662 prev_prio=120 prev_state=S ==> next_comm=kworker/0:0 next_pid=13696 next_prio=120\\n\\', // @suppress longLineCheck
      '     kworker/0:0-13696 [000] 50260.647590: sched_wakeup: comm=mmcqd/0 pid=95 prio=120 success=1 target_cpu=000\\n\\', // @suppress longLineCheck
      '     kworker/0:0-13696 [000] 50260.647602: sched_wakeup: comm=adbd pid=14582 prio=120 success=1 target_cpu=000\\n\\', // @suppress longLineCheck
      '     kworker/0:0-13696 [000] 50260.647610: sched_switch: prev_comm=kworker/0:0 prev_pid=13696 prev_prio=120 prev_state=S ==> next_comm=adbd next_pid=14582 next_prio=120\\n\\', // @suppress longLineCheck
      '            adbd-14582 [000] 50260.647722: sched_wakeup: comm=adbd pid=14584 prio=120 success=1 target_cpu=000\\n\\', // @suppress longLineCheck
      '            adbd-14582 [000] 50260.647756: sched_switch: prev_comm=adbd prev_pid=14582 prev_prio=120 prev_state=S ==> next_comm=adbd next_pid=14584 next_prio=120\\n\\', // @suppress longLineCheck
      '            adbd-14584 [000] 50260.647833: sched_switch: prev_comm=adbd prev_pid=14584 prev_prio=120 prev_state=S ==> next_comm=mmcqd/0 next_pid=95 next_prio=120\\n\\', // @suppress longLineCheck
      '         mmcqd/0-95    [000] 50260.647846: sched_switch: prev_comm=mmcqd/0 prev_pid=95 prev_prio=120 prev_state=S ==> next_comm=WebViewCoreThre next_pid=11043 next_prio=120\\n\\', // @suppress longLineCheck
      ' WebViewCoreThre-11043 [000] 50260.648275: sched_switch: prev_comm=WebViewCoreThre prev_pid=11043 prev_prio=120 prev_state=S ==> next_comm=swapper next_pid=0 next_prio=120\\n";', // @suppress longLineCheck
      '  <\/script>',
      '<\/body>',
      '<\/html>'
    ];
    var html_text = html_lines.join('\n');
    assertTrue(tracing.importer.LinuxPerfImporter.canImport(html_text));

    var expected_event_lines = [
      '# tracer: nop',
      '#',
      '#           TASK-PID    CPU#    TIMESTAMP  FUNCTION',
      '#              | |       |          |         |',
      '          atrace-14662 [000] 50260.647576: sched_switch: prev_comm=atrace prev_pid=14662 prev_prio=120 prev_state=S ==> next_comm=kworker/0:0 next_pid=13696 next_prio=120', // @suppress longLineCheck
      '     kworker/0:0-13696 [000] 50260.647590: sched_wakeup: comm=mmcqd/0 pid=95 prio=120 success=1 target_cpu=000', // @suppress longLineCheck
      '     kworker/0:0-13696 [000] 50260.647602: sched_wakeup: comm=adbd pid=14582 prio=120 success=1 target_cpu=000', // @suppress longLineCheck
      '     kworker/0:0-13696 [000] 50260.647610: sched_switch: prev_comm=kworker/0:0 prev_pid=13696 prev_prio=120 prev_state=S ==> next_comm=adbd next_pid=14582 next_prio=120', // @suppress longLineCheck
      '            adbd-14582 [000] 50260.647722: sched_wakeup: comm=adbd pid=14584 prio=120 success=1 target_cpu=000', // @suppress longLineCheck
      '            adbd-14582 [000] 50260.647756: sched_switch: prev_comm=adbd prev_pid=14582 prev_prio=120 prev_state=S ==> next_comm=adbd next_pid=14584 next_prio=120', // @suppress longLineCheck
      '            adbd-14584 [000] 50260.647833: sched_switch: prev_comm=adbd prev_pid=14584 prev_prio=120 prev_state=S ==> next_comm=mmcqd/0 next_pid=95 next_prio=120', // @suppress longLineCheck
      '         mmcqd/0-95    [000] 50260.647846: sched_switch: prev_comm=mmcqd/0 prev_pid=95 prev_prio=120 prev_state=S ==> next_comm=WebViewCoreThre next_pid=11043 next_prio=120', // @suppress longLineCheck
      ' WebViewCoreThre-11043 [000] 50260.648275: sched_switch: prev_comm=WebViewCoreThre prev_pid=11043 prev_prio=120 prev_state=S ==> next_comm=swapper next_pid=0 next_prio=120' // @suppress longLineCheck
    ];
    var expected_event_text = expected_event_lines.join('\n');
    var res =
        tracing.importer.LinuxPerfImporter._extractEventsFromSystraceHTML(
            html_text, true);
    var actual_event_text = res.lines.join('\n');
    assertEquals(actual_event_text, expected_event_text);
  });

  test('importOneSequence', function() {
    var lines = [
      '          <idle>-0     [001]  4467.843475: sched_switch: ' +
          'prev_comm=swapper prev_pid=0 prev_prio=120 prev_state=R ==> ' +
          'next_comm=SurfaceFlinger next_pid=178 next_prio=112',

      '  SurfaceFlinger-178   [001]  4467.843536: sched_switch: ' +
          'prev_comm=SurfaceFlinger prev_pid=178 prev_prio=112 ' +
          'prev_state=S ==> next_comm=kworker/u:2 next_pid=2844 ' +
          'next_prio=120',

      '     kworker/u:2-2844  [001]  4467.843567: sched_switch: ' +
          'prev_comm=kworker/u:2 prev_pid=2844 prev_prio=120 ' +
          'prev_state=S ==> next_comm=swapper next_pid=0 next_prio=120'
    ];
    var m = new tracing.TraceModel(lines.join('\n'), false);
    assertEquals(0, m.importErrors.length);

    var c = m.kernel.cpus[1];
    assertEquals(2, c.slices.length);

    assertEquals('SurfaceFlinger', c.slices[0].title);
    assertEquals(4467843.475, c.slices[0].start);
    assertAlmostEquals(.536 - .475, c.slices[0].duration);
  });

  test('importOneSequenceWithSpacyThreadName', function() {
    var lines = [
      '          <idle>-0     [001]  4467.843475: sched_switch: ' +
          'prev_comm=swapper prev_pid=0 prev_prio=120 prev_state=R ==> ' +
          'next_comm=Surface Flinger  next_pid=178 next_prio=112',

      'Surface Flinger -178   [001]  4467.843536: sched_switch: ' +
          'prev_comm=Surface Flinger  prev_pid=178 prev_prio=112 ' +
          'prev_state=S ==> next_comm=kworker/u:2 next_pid=2844 ' +
          'next_prio=120',

      '     kworker/u:2-2844  [001]  4467.843567: sched_switch: ' +
          'prev_comm=kworker/u:2 prev_pid=2844 prev_prio=120 ' +
          'prev_state=S ==> next_comm=swapper next_pid=0 next_prio=120'
    ];
    var m = new tracing.TraceModel(lines.join('\n'), false);
    assertEquals(0, m.importErrors.length);

    var c = m.kernel.cpus[1];
    assertEquals(2, c.slices.length);

    assertEquals('Surface Flinger ', c.slices[0].title);
    assertEquals(4467843.475, c.slices[0].start);
    assertAlmostEquals(.536 - .475, c.slices[0].duration);
  });

  test('importWithNewline', function() {
    var lines = [
      ''
    ];
    var m = new tracing.TraceModel(lines.join('\n'));
    assertEquals(0, m.importErrors.length);
  });

  test('clockSync', function() {
    var lines = [
      '          <idle>-0     [001]  4467.843475: sched_switch: ' +
          'prev_comm=swapper prev_pid=0 prev_prio=120 prev_state=R ' +
          '==> next_comm=SurfaceFlinger next_pid=178 next_prio=112',
      '  SurfaceFlinger-178   [001]  4467.843536: sched_switch: ' +
          'prev_comm=SurfaceFlinger prev_pid=178 prev_prio=112 ' +
          'prev_state=S ==> next_comm=kworker/u:2 next_pid=2844 ' +
          'next_prio=120',
      '     kworker/u:2-2844  [001]  4467.843567: sched_switch: ' +
          'prev_comm=kworker/u:2 prev_pid=2844 prev_prio=120 ' +
          'prev_state=S ==> next_comm=swapper next_pid=0 ' +
          'next_prio=120',
      '     kworker/u:2-2844  [001]  4467.843000: 0: ' +
          'trace_event_clock_sync: parent_ts=0.1'
    ];
    var m = new tracing.TraceModel(lines.join('\n'), false);
    assertEquals(0, m.importErrors.length);

    var c = m.kernel.cpus[1];
    assertEquals(2, c.slices.length);

    assertAlmostEquals((467.843475 - (467.843 - 0.1)) * 1000,
                       c.slices[0].start);
  });

  test('clockSyncMarkWrite', function() {
    var lines = [
      'systrace.sh-8170  [001] 15180.978813: sched_switch: ' +
          'prev_comm=systrace.sh prev_pid=8170 prev_prio=120 ' +
          'prev_state=x ==> next_comm=kworker/1:0 next_pid=7873 ' +
          'next_prio=120',
      ' kworker/1:0-7873  [001] 15180.978836: sched_switch: ' +
          'prev_comm=kworker/1:0 prev_pid=7873 prev_prio=120 ' +
          'prev_state=S ==> next_comm=debugd next_pid=4404 next_prio=120',
      '     debugd-4404  [001] 15180.979010: sched_switch: prev_comm=debugd ' +
          'prev_pid=4404 prev_prio=120 prev_state=S ==> ' +
          'next_comm=dbus-daemon next_pid=510 next_prio=120',
      'systrace.sh-8182  [000] 15186.203900: tracing_mark_write: ' +
          'trace_event_clock_sync: parent_ts=0'
    ];
    var m = new tracing.TraceModel(lines.join('\n'), false);
    assertEquals(0, m.importErrors.length);

    var c = m.kernel.cpus[1];
    assertEquals(2, c.slices.length);

    assertAlmostEquals((15180.978813 - 0) * 1000, c.slices[0].start);
  });
});
