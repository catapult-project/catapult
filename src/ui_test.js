base.require('ui');

'use strict';

base.unittest.testSuite('ui', function() {
  var TestElement = ui.define('div');
  TestElement.prototype = {
    __proto__: HTMLDivElement.prototype,

    decorate: function() {
      if (!this.decorateCallCount)
        this.decorateCallCount = 0;
      this.decorateCallCount++;
    }
  };

  var Base = ui.define('div');
  Base.prototype = {
    __proto__: HTMLDivElement.prototype,
    decorate: function() {
      this.decoratedAsBase = true;
    },
    set baseProperty(v) {
      this.basePropertySet = v;
    }
  };

  test('decorateOnceViaNew', function() {
    var testElement = new TestElement();
    assertEquals(1, testElement.decorateCallCount);
  });

  test('decorateOnceDirectly', function() {
    var testElement = document.createElement('div');
    ui.decorate(testElement, TestElement);
    assertEquals(1, testElement.decorateCallCount);
  });

  test('basicDefines', function() {
    assertEquals('div', Base.toString());
    var baseInstance = new Base();
    assertTrue(baseInstance instanceof Base);

    assertTrue(baseInstance.decoratedAsBase);

    baseInstance.basePropertySet = 7;
    assertEquals(7, baseInstance.basePropertySet);
  });

  test('subclassing', function() {
    var Sub = ui.define('Sub', Base);
    assertEquals('div::sub', Sub.toString());
    Sub.prototype = {
      __proto__: Base.prototype,
      decorate: function() {
        this.decoratedAsSub = true;
      }
    };

    var subInstance = new Sub();
    assertTrue(subInstance instanceof Sub);
    assertTrue(subInstance.decoratedAsSub);

    assertTrue(subInstance instanceof Base);
    assertTrue(subInstance.decoratedAsBase);

    subInstance.baseProperty = true;
    assertTrue(subInstance.basePropertySet);
  });
});
