base.require('tracing.test_utils');
base.require('tracing.timeline_viewport');
base.require('tracing.tracks.ruler_track');

'use strict';

base.unittest.testSuite('tracing.tracks.ruler_track', function() {
  test('instantiate', function() {
    var viewport = document.createElement('div');
    var track = tracing.tracks.RulerTrack();
    track.viewport = new tracing.TimelineViewport(viewport);
    track.viewport.setPanAndScale(0,
        track.clientWidth / 1000);
    viewport.appendChild(track);

    this.addHTMLOutput(viewport);
  });
});
