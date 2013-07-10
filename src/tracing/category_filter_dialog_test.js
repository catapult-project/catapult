// Copyright (c) 2013 The Chromium Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

'use strict';

base.require('base.settings');
base.require('tracing.test_utils');
base.require('tracing.category_filter_dialog');

base.unittest.testSuite('tracing.category_filter_dialog', function() {
  test('categoryFilterDialog_UpdateForm_NoSettings', function() {
    var settings = new base.Settings();

    var dlg = new tracing.CategoryFilterDialog();
    dlg.categories = ['one', 'two', 'three'];
    dlg.settings = settings;
    dlg.settings_key = 'key';
    dlg.updateForm_();

    var checkboxes = dlg.formEl_.getElementsByTagName('input');
    assertEquals(3, checkboxes.length);
    assertEquals('one', checkboxes[0].id);
    assertEquals('one', checkboxes[0].value);
    assertEquals(true, checkboxes[0].checked);
    assertEquals('three', checkboxes[1].id);
    assertEquals('three', checkboxes[1].value);
    assertEquals(true, checkboxes[1].checked);
    assertEquals('two', checkboxes[2].id);
    assertEquals('two', checkboxes[2].value);
    assertEquals(true, checkboxes[2].checked);
    var labels = dlg.formEl_.getElementsByTagName('label');
    assertEquals(3, labels.length);
    assertEquals('one', labels[0].textContent);
    assertEquals('three', labels[1].textContent);
    assertEquals('two', labels[2].textContent);
  });
});
