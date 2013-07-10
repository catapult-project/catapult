// Copyright (c) 2013 The Chromium Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

'use strict';

base.require('ui.list_and_associated_view');

base.unittest.testSuite('ui.list_and_associated_view', function() {
  var ListAndAssociatedView = ui.ListAndAssociatedView;

  var SimpleView = ui.define('div');
  SimpleView.prototype = {
    __proto__: HTMLDivElement.prototype,

    decorate: function() {
      this.item_ = undefined;
    },

    set item(item) {
      this.item_ = item;
    },
    get item() {
      return this.item_;
    }
  };

  test('listViewNamingWithField', function() {
    var lav = new ListAndAssociatedView();
    var list = [
      {x: '1'},
      {x: '2'},
      {x: '3'}
    ];
    var view = new SimpleView();

    lav.list = list;
    lav.listProperty = 'x';
    lav.view = view;
    lav.viewProperty = 'item';

    var lavListView = lav.listView;
    assertEquals(3, lavListView.children.length);
    assertEquals('1', lavListView.children[0].textContent);
  });

  test('listViewNamingWithProperty', function() {
    var lav = new ListAndAssociatedView();

    function X(x) {
      this.x = x;
    }
    X.prototype = {
      get title() {
        return this.x;
      }
    };

    var list = [
      new X('1'),
      new X('2'),
      new X('3')
    ];
    var view = new SimpleView();

    lav.list = list;
    lav.listProperty = 'title';
    lav.view = view;
    lav.viewProperty = 'item';

    var lavListView = lav.listView;
    assertEquals(3, lavListView.children.length);
    assertEquals('1', lavListView.children[0].textContent);
  });

  test('selectionChangesView', function() {
    var lav = new ListAndAssociatedView();
    var list = [
      {x: '1'},
      {x: '2'},
      {x: '3'}
    ];
    var view = new SimpleView();

    lav.list = list;
    lav.listProperty = 'x';
    lav.view = view;
    lav.viewProperty = 'item';
    var lavListView = lav.listView;

    assertEquals(list[0], view.item);
    lavListView.children[1].selected = true;
    assertEquals(list[1], view.item);
  });
});
