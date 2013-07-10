// Copyright (c) 2013 The Chromium Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

'use strict';

base.require('base.settings');
base.require('tracing.test_utils');
base.require('tracing.record_selection_dialog');

base.unittest.testSuite('tracing.record_selection_dialog', function() {
  test('recordSelectionDialog_UpdateForm_NoSettings', function() {
    var settings = new base.Settings();

    var dlg = new tracing.RecordSelectionDialog();
    dlg.categories = ['disabled-by-default-one', 'two', 'three'];
    dlg.settings = settings;
    dlg.settings_key = 'key';
    dlg.updateForm_();

    var checkboxes = dlg.formEl_.getElementsByTagName('input');
    assertEquals(3, checkboxes.length);
    assertEquals('three', checkboxes[0].id);
    assertEquals('three', checkboxes[0].value);
    assertEquals(true, checkboxes[0].checked);
    assertEquals('two', checkboxes[1].id);
    assertEquals('two', checkboxes[1].value);
    assertEquals(true, checkboxes[1].checked);
    assertEquals('disabled-by-default-one', checkboxes[2].id);
    assertEquals('disabled-by-default-one', checkboxes[2].value);
    assertEquals(false, checkboxes[2].checked);

    assertEquals('', dlg.categoryFilter());

    var labels = dlg.formEl_.getElementsByTagName('label');
    assertEquals(3, labels.length);
    assertEquals('three', labels[0].textContent);
    assertEquals('two', labels[1].textContent);
    assertEquals('one', labels[2].textContent);
  });

  test('recordSelectionDialog_UpdateForm_Settings', function() {
    var settings = new base.Settings();
    settings.set('two', true, 'categories');
    settings.set('three', false, 'categories');

    var dlg = new tracing.RecordSelectionDialog();
    dlg.categories = ['disabled-by-default-one'];
    dlg.settings = settings;
    dlg.settings_key = 'categories';
    dlg.updateForm_();

    var checkboxes = dlg.formEl_.getElementsByTagName('input');
    assertEquals(3, checkboxes.length);
    assertEquals('three', checkboxes[0].id);
    assertEquals('three', checkboxes[0].value);
    assertEquals(false, checkboxes[0].checked);
    assertEquals('two', checkboxes[1].id);
    assertEquals('two', checkboxes[1].value);
    assertEquals(true, checkboxes[1].checked);
    assertEquals('disabled-by-default-one', checkboxes[2].id);
    assertEquals('disabled-by-default-one', checkboxes[2].value);
    assertEquals(false, checkboxes[2].checked);

    assertEquals('-three', dlg.categoryFilter());

    var labels = dlg.formEl_.getElementsByTagName('label');
    assertEquals(3, labels.length);
    assertEquals('three', labels[0].textContent);
    assertEquals('two', labels[1].textContent);
    assertEquals('one', labels[2].textContent);
  });

  test('recordSelectionDialog_UpdateForm_DisabledByDefault', function() {
    var settings = new base.Settings();

    var dlg = new tracing.RecordSelectionDialog();
    dlg.categories = ['disabled-by-default-bar', 'baz'];
    dlg.settings = settings;
    dlg.settings_key = 'categories';
    dlg.updateForm_();

    assertEquals('', dlg.categoryFilter());

    var inputs =
        dlg.formEl_.querySelector('input#disabled-by-default-bar').click();

    assertEquals('disabled-by-default-bar', dlg.categoryFilter());

    assertEquals(false,
        settings.get('disabled-by-default-foo', false, 'categories'));
  });

  test('selectAll', function() {
    var settings = new base.Settings();
    settings.set('two', true, 'categories');
    settings.set('three', false, 'categories');

    var dlg = new tracing.RecordSelectionDialog();
    dlg.categories = ['disabled-by-default-one'];
    dlg.settings = settings;
    dlg.settings_key = 'categories';
    dlg.updateForm_();
  });

  test('selectNone', function() {
    var settings = new base.Settings();
    settings.set('two', true, 'categories');
    settings.set('three', false, 'categories');

    var dlg = new tracing.RecordSelectionDialog();
    dlg.categories = ['disabled-by-default-one'];
    dlg.settings = settings;
    dlg.settings_key = 'categories';
    dlg.updateForm_();

    // Enables the three option, two already enabled.
    dlg.formEl_.querySelector('.default-enabled-categories .all-btn').click();
    assertEquals('', dlg.categoryFilter());
    assertEquals(true, settings.get('three', false, 'categories'));

    // Disables three and two.
    dlg.formEl_.
        querySelector('.default-enabled-categories .none-btn').click();
    assertEquals('-three,-two', dlg.categoryFilter());
    assertEquals(false, settings.get('two', false, 'categories'));
    assertEquals(false, settings.get('three', false, 'categories'));

    // Turn categories back on so they can be ignored.
    dlg.formEl_.querySelector('.default-enabled-categories .all-btn').click();

    // Enables disabled category.
    dlg.formEl_.
        querySelector('.default-disabled-categories .all-btn').click();
    assertEquals('disabled-by-default-one', dlg.categoryFilter());
    assertEquals(true,
        settings.get('disabled-by-default-one', false, 'categories'));

    // Turn disabled by default back off.
    dlg.formEl_.
        querySelector('.default-disabled-categories .none-btn').click();
    assertEquals('', dlg.categoryFilter());
    assertEquals(false,
        settings.get('disabled-by-default-one', false, 'categories'));
  });
});
