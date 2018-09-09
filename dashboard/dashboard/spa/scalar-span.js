/* Copyright 2018 The Chromium Authors. All rights reserved.
   Use of this source code is governed by a BSD-style license that can be
   found in the LICENSE file.
*/
'use strict';
tr.exportTo('cp', () => {
  class ScalarSpan extends Polymer.Element {
    static get is() { return 'scalar-span'; }

    change_(unit, value) {
      return ScalarSpan.getChange(unit, value);
    }

    format_(unit, value, maximumFractionDigits, unitPrefix) {
      return !unit ? '' : unit.format(
          value, {maximumFractionDigits, unitPrefix});
    }
  }

  ScalarSpan.getChange = (unit, value) => {
    if (!unit) return '';
    if (!unit.isDelta) return '';
    if (unit.improvementDirection === tr.b.ImprovementDirection.DONT_CARE) {
      return '';
    }
    if (value === 0) return '';
    if (unit.improvementDirection ===
        tr.b.ImprovementDirection.BIGGER_IS_BETTER) {
      return value > 0 ? 'improvement' : 'regression';
    }
    return value < 0 ? 'improvement' : 'regression';
  };

  ScalarSpan.properties = {
    maximumFractionDigits: {type: Number},
    unit: {type: Object},
    unitPrefix: {type: Object},
    value: {type: Number},
  };

  customElements.define(ScalarSpan.is, ScalarSpan);

  return {ScalarSpan};
});
