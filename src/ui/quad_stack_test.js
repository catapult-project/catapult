base.require('base.unittest');
base.require('base.bbox2');
base.require('ui.quad_stack');

'use strict';

base.unittest.testSuite('ui.quad_stack', function() {
  test('instantiate', function() {
    var quads = [
      base.Quad.FromXYWH(0, -100, 100, 400),
      base.Quad.FromXYWH(0, 0, 100, 25),
      base.Quad.FromXYWH(100, 0, 10, 100)
    ];
    quads[0].stackingGroupId = 0;
    quads[1].stackingGroupId = 1;
    quads[2].stackingGroupId = 2;

    var quadsBbox = new base.BBox2();
    quads.forEach(function(quad) { quadsBbox.addQuad(quad); });

    var stack = new ui.QuadStack();
    stack.quads = quads;
    var deviceViewportSizeForFrame = {width: 100, height: 100};
    stack.viewport = new ui.QuadViewViewport(quadsBbox,
        0.5, deviceViewportSizeForFrame);
    stack.style.border = '1px solid black';

    this.addHTMLOutput(stack);
  });
});
