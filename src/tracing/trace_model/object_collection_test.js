// Copyright (c) 2013 The Chromium Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

'use strict';

base.require('tracing.test_utils');
base.require('tracing.trace_model.object_collection');

base.unittest.testSuite('tracing.trace_model.object_collection', function() {
  var TestObjectInstance = function(parent, id, category, name, creationTs) {
    tracing.trace_model.ObjectInstance.call(
        this, parent, id, category, name, creationTs);
  };

  TestObjectInstance.prototype = {
    __proto__: tracing.trace_model.ObjectInstance.prototype
  };

  test('objectInstanceSubtype', function() {
    // Register that TestObjects are bound to TestObjectInstance.
    tracing.trace_model.ObjectInstance.register(
        'TestObject', TestObjectInstance);
    try {
      var collection = new tracing.trace_model.ObjectCollection({ });
      collection.idWasCreated(
          '0x1000', 'cc', 'Frame', 10);
      collection.idWasDeleted(
          '0x1000', 'cc', 'Frame', 15);
      collection.idWasCreated(
          '0x1000', 'skia', 'TestObject', 20);
      collection.idWasDeleted(
          '0x1000', 'skia', 'TestObject', 25);

      var testFrame = collection.getObjectInstanceAt('0x1000', 10);
      assertTrue(testFrame instanceof tracing.trace_model.ObjectInstance);
      assertFalse(testFrame instanceof TestObjectInstance);

      var testObject = collection.getObjectInstanceAt('0x1000', 20);
      assertTrue(testObject instanceof tracing.trace_model.ObjectInstance);
      assertTrue(testObject instanceof TestObjectInstance);
    } finally {
      tracing.trace_model.ObjectInstance.unregister('TestObject');
    }
  });

  test('twoSnapshots', function() {
    var collection = new tracing.trace_model.ObjectCollection({});
    collection.idWasCreated(
        '0x1000', 'cat', 'Frame', 10);
    collection.addSnapshot(
        '0x1000', 'cat', 'Frame', 10, {foo: 1});
    collection.addSnapshot(
        '0x1000', 'cat', 'Frame', 20, {foo: 2});

    collection.updateBounds();
    assertEquals(10, collection.bounds.min);
    assertEquals(20, collection.bounds.max);

    var s0 = collection.getSnapshotAt('0x1000', 1);
    assertUndefined(s0);

    var s1 = collection.getSnapshotAt('0x1000', 10);
    assertEquals(s1.args.foo, 1);

    var s2 = collection.getSnapshotAt('0x1000', 15);
    assertEquals(s2.args.foo, 1);
    assertEquals(s1, s2);

    var s3 = collection.getSnapshotAt('0x1000', 20);
    assertEquals(s3.args.foo, 2);
    assertEquals(s1.object, s3.object);

    var s4 = collection.getSnapshotAt('0x1000', 25);
    assertEquals(s4, s3);
  });

  test('twoObjectsSharingOneID', function() {
    var collection = new tracing.trace_model.ObjectCollection({});
    collection.idWasCreated(
        '0x1000', 'cc', 'Frame', 10);
    collection.idWasDeleted(
        '0x1000', 'cc', 'Frame', 15);
    collection.idWasCreated(
        '0x1000', 'skia', 'Picture', 20);
    collection.idWasDeleted(
        '0x1000', 'skia', 'Picture', 25);

    var frame = collection.getObjectInstanceAt('0x1000', 10);
    assertEquals('cc', frame.category);
    assertEquals('Frame', frame.name);

    var picture = collection.getObjectInstanceAt('0x1000', 20);
    assertEquals('skia', picture.category);
    assertEquals('Picture', picture.name);

    var typeNames = base.dictionaryKeys(collection.getAllInstancesByTypeName());
    typeNames.sort();
    assertArrayEquals(
        ['Frame', 'Picture'],
        typeNames);
    assertArrayEquals(
        [frame],
        collection.getAllInstancesByTypeName()['Frame']);
    assertArrayEquals(
        [picture],
        collection.getAllInstancesByTypeName()['Picture']);
  });

  test('createSnapDelete', function() {
    var collection = new tracing.trace_model.ObjectCollection({});
    collection.idWasCreated(
        '0x1000', 'cat', 'Frame', 10);
    collection.addSnapshot(
        '0x1000', 'cat', 'Frame', 10, {foo: 1});
    collection.idWasDeleted(
        '0x1000', 'cat', 'Frame', 15);

    collection.updateBounds();
    assertEquals(10, collection.bounds.min);
    assertEquals(15, collection.bounds.max);

    var s10 = collection.getSnapshotAt('0x1000', 10);
    var i10 = s10.objectInstance;
    assertEquals(10, i10.creationTs);
    assertEquals(15, i10.deletionTs);
  });

  test('boundsOnUndeletedObject', function() {
    var collection = new tracing.trace_model.ObjectCollection({});
    collection.idWasCreated(
        '0x1000', 'cat', 'Frame', 10);
    collection.addSnapshot(
        '0x1000', 'cat', 'Frame', 15, {foo: 1});

    collection.updateBounds();
    assertEquals(collection.bounds.min, 10);
    assertEquals(collection.bounds.max, 15);
  });

  test('autoDelete', function() {
    var collection = new tracing.trace_model.ObjectCollection({});
    collection.idWasCreated(
        '0x1000', 'cat', 'Frame', 10);
    collection.addSnapshot(
        '0x1000', 'cat', 'Frame', 10, {foo: 1});
    collection.autoDeleteObjects(15);

    var s10 = collection.getSnapshotAt('0x1000', 10);
    var i10 = s10.objectInstance;
    assertEquals(i10.deletionTs, 15);
  });
});
