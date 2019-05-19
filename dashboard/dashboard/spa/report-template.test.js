/* Copyright 2018 The Chromium Authors. All rights reserved.
   Use of this source code is governed by a BSD-style license that can be
   found in the LICENSE file.
*/
'use strict';

import DescribeRequest from './describe-request.js';
import MenuInput from './menu-input.js';
import ReportTemplate from './report-template.js';
import ReportTemplateRequest from './report-template-request.js';
import TestSuitesRequest from './test-suites-request.js';
import {CHAIN, ENSURE, UPDATE} from './simple-redux.js';
import {STORE} from './element-base.js';
import {afterRender} from './utils.js';
import {assert} from 'chai';

suite('report-template', function() {
  async function fixture() {
    const template = document.createElement('report-template');
    template.statePath = 'test';
    await STORE.dispatch(CHAIN(
        ENSURE('test'),
        UPDATE('test', ReportTemplate.buildState({
          id: 42,
          name: 'test name',
          owners: 'me@chromium.org',
          rows: [
            ReportTemplate.newTemplateRow({
              label: 'label',
              suites: ['suite'],
              measurement: 'measurement',
              bots: ['master:bot'],
              cases: ['case'],
            }),
          ],
          statistic: MenuInput.buildState({
            options: ['avg', 'std'],
            selectedOptions: ['avg'],
          }),
          url: 'http://example.com',
        }))));
    document.body.appendChild(template);
    await afterRender();
    return template;
  }

  let originalFetch;
  let templateBody;
  setup(() => {
    originalFetch = window.fetch;
    window.fetch = async(url, options) => {
      return {
        ok: true,
        async json() {
          if (url === ReportTemplateRequest.URL) {
            templateBody = new Map(options.body);
            return [];
          }
          if (url === TestSuitesRequest.URL) {
            return ['suite'];
          }
          if (url === DescribeRequest.URL) {
            return {
              bots: ['master:bot'],
              measurements: ['measurement'],
              cases: ['case'],
            };
          }
        },
      };
    };
  });
  teardown(() => {
    for (const child of document.body.children) {
      if (!child.matches('report-template')) continue;
      document.body.removeChild(child);
    }
    window.fetch = originalFetch;
  });

  test('canSave', async function() {
    assert.isTrue(ReportTemplate.canSave(
        'name', 'owner@chromium.org', {selectedOptions: ['avg']}, [{
          label: 'label',
          suite: {selectedOptions: ['suite']},
          measurement: {selectedOptions: ['measurement']},
          bot: {selectedOptions: ['bot']},
        }]));
    assert.isFalse(ReportTemplate.canSave(
        '', 'owner@chromium.org', {selectedOptions: ['avg']}, [{
          label: 'label',
          suite: {selectedOptions: ['suite']},
          measurement: {selectedOptions: ['measurement']},
          bot: {selectedOptions: ['bot']},
        }]));
    assert.isFalse(ReportTemplate.canSave(
        'name', '', {selectedOptions: ['avg']}, [{
          label: 'label',
          suite: {selectedOptions: ['suite']},
          measurement: {selectedOptions: ['measurement']},
          bot: {selectedOptions: ['bot']},
        }]));
    assert.isFalse(ReportTemplate.canSave(
        'name', 'owner@chromium.org', {selectedOptions: []}, [{
          label: 'label',
          suite: {selectedOptions: ['suite']},
          measurement: {selectedOptions: ['measurement']},
          bot: {selectedOptions: ['bot']},
        }]));
    assert.isFalse(ReportTemplate.canSave(
        'name', 'owner@chromium.org', {selectedOptions: ['avg']}, [{
          label: '',
          suite: {selectedOptions: ['suite']},
          measurement: {selectedOptions: ['measurement']},
          bot: {selectedOptions: ['bot']},
        }]));
    assert.isFalse(ReportTemplate.canSave(
        'name', 'owner@chromium.org', {selectedOptions: ['avg']}, [{
          label: 'label',
          suite: {selectedOptions: []},
          measurement: {selectedOptions: ['measurement']},
          bot: {selectedOptions: ['bot']},
        }]));
    assert.isFalse(ReportTemplate.canSave(
        'name', 'owner@chromium.org', {selectedOptions: ['avg']}, [{
          label: 'label',
          suite: {selectedOptions: ['suite']},
          measurement: {selectedOptions: []},
          bot: {selectedOptions: ['bot']},
        }]));
    assert.isFalse(ReportTemplate.canSave(
        'name', 'owner@chromium.org', {selectedOptions: ['avg']}, [{
          label: 'label',
          suite: {selectedOptions: ['suite']},
          measurement: {selectedOptions: ['measurement', 'another']},
          bot: {selectedOptions: ['bot']},
        }]));
    assert.isFalse(ReportTemplate.canSave(
        'name', 'owner@chromium.org', {selectedOptions: ['avg']}, [{
          label: 'label',
          suite: {selectedOptions: ['suite']},
          measurement: {selectedOptions: ['measurement']},
          bot: {selectedOptions: []},
        }]));
  });

  test('addRemoveRow', async function() {
    const template = await fixture();
    assert.lengthOf(template.rows, 1);

    template.shadowRoot.querySelector('iron-icon').click();
    await afterRender();
    assert.lengthOf(template.rows, 2);

    template.shadowRoot.querySelectorAll('iron-icon')[3].click();
    await afterRender();
    assert.lengthOf(template.rows, 1);
  });

  test('save', async function() {
    const template = await fixture();
    template.$.save.click();
    await afterRender();
    assert.strictEqual('42', templateBody.get('id'));
    assert.strictEqual('test name', templateBody.get('name'));
    assert.strictEqual('me@chromium.org', templateBody.get('owners'));
    assert.deepEqual(JSON.parse(templateBody.get('template')), {
      url: 'http://example.com',
      statistics: ['avg'],
      rows: [{
        label: 'label',
        suites: ['suite'],
        measurement: 'measurement',
        bots: ['master:bot'],
        cases: ['case'],
      }],
    });
  });
});
