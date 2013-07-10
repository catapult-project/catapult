// Copyright (c) 2013 The Chromium Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

'use strict';

base.require('ui');

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

  test('toString', function() {
    assertEquals('div', Base.toString());

    var Sub = ui.define('Sub', Base);
    assertEquals('div::sub', Sub.toString());

    var SubSub = ui.define('Marine', Sub);
    assertEquals('div::sub::marine', SubSub.toString());
  });

  test('basicDefines', function() {
    var baseInstance = new Base();
    assertTrue(baseInstance instanceof Base);
    assertTrue(baseInstance.decoratedAsBase);

    baseInstance.basePropertySet = 7;
    assertEquals(7, baseInstance.basePropertySet);
  });

  test('subclassing', function() {
    var Sub = ui.define('Sub', Base);
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
    assertFalse(subInstance.decoratedAsBase);

    subInstance.baseProperty = true;
    assertTrue(subInstance.basePropertySet);
  });

  var NoArgs = ui.define('div');
  NoArgs.prototype = {
    __proto__: HTMLDivElement.prototype,
    decorate: function() {
      this.noArgsDecorated_ = true;
    },
    get noArgsDecorated() {
      return this.noArgsDecorated_;
    }
  };

  var Args = ui.define('args', NoArgs);
  Args.prototype = {
    __proto__: NoArgs.prototype,
    decorate: function(first) {
      this.first_ = first;
      this.argsDecorated_ = true;
    },
    get first() {
      return this.first_;
    },
    get argsDecorated() {
      return this.argsDecorated_;
    }
  };

  var ArgsChild = ui.define('child', Args);
  ArgsChild.prototype = {
    __proto__: Args.prototype,
    decorate: function(_, second) {
      this.second_ = second;
      this.argsChildDecorated_ = true;
    },
    get second() {
      return this.second_;
    },
    get decorated() {
      return this.decorated_;
    },
    get argsChildDecorated() {
      return this.argsChildDecorated_ = true;
    }
  };

  var ArgsDecoratingChild = ui.define('child', Args);
  ArgsDecoratingChild.prototype = {
    __proto__: Args.prototype,
    decorate: function(first, second) {
      Args.prototype.decorate.call(this, first);
      this.second_ = second;
      this.argsDecoratingChildDecorated_ = true;
    },
    get second() {
      return this.second_;
    },
    get decorated() {
      return this.decorated_;
    },
    get argsDecoratingChildDecorated() {
      return this.argsChildDecorated_ = true;
    }
  };

  test('decorate_noArguments', function() {
    var noArgs;
    assertDoesNotThrow(function() {
      noArgs = new NoArgs();
    });
    assertTrue(noArgs.noArgsDecorated);
  });

  test('decorate_arguments', function() {
    var args = new Args('this is first');
    assertEquals('this is first', args.first);
    assertTrue(args.argsDecorated);
    assertFalse(args.noArgsDecorated);
  });

  test('decorate_subclassArguments', function() {
    var argsChild = new ArgsChild('this is first', 'and second');
    assertUndefined(argsChild.first);
    assertEquals('and second', argsChild.second);

    assertTrue(argsChild.argsChildDecorated);
    assertFalse(argsChild.argsDecorated);
    assertFalse(argsChild.noArgsDecorated);
  });

  test('decorate_subClassCallsParentDecorate', function() {
    var argsDecoratingChild = new ArgsDecoratingChild(
        'this is first', 'and second');
    assertEquals('this is first', argsDecoratingChild.first);
    assertEquals('and second', argsDecoratingChild.second);
    assertTrue(argsDecoratingChild.argsDecoratingChildDecorated);
    assertTrue(argsDecoratingChild.argsDecorated);
    assertFalse(argsDecoratingChild.noArgsDecorated);
  });
});
