/* Copyright 2019 The Chromium Authors. All rights reserved.
   Use of this source code is governed by a BSD-style license that can be
   found in the LICENSE file.
*/
'use strict';

import {html} from 'lit-element';
import {crbug, plural} from './utils.js';
import ExistingBugRequest from './existing-bug-request.js';

function analyzeTriaged(triagedAlerts) {
  const alertCountByBugId = new Map();
  for (const alert of triagedAlerts) {
    if (alert.bugId < 0) continue;
    alertCountByBugId.set(alert.bugId,
        1 + (alertCountByBugId.get(alert.bugId) || 0));
  }
  let bugId = 0;
  let maxAlertCount = 0;
  for (const [triagedBugId, alertCount] of alertCountByBugId) {
    if (alertCount > maxAlertCount) {
      maxAlertCount = alertCount;
      bugId = triagedBugId;
    }
  }

  return {bugId, maxAlertCount};
}

function analyzeAlerts(alerts) {
  let maxPctDelta = 0;
  for (const alert of alerts) {
    maxPctDelta = Math.max(maxPctDelta, Math.abs(alert.percentDeltaValue));
  }
  return {maxPctDelta};
}

export const MIN_PCT_DELTA = 0.02;

export function autotriage(alerts, triagedAlerts) {
  const {maxPctDelta} = analyzeAlerts(alerts);
  const {bugId, maxAlertCount} = analyzeTriaged(triagedAlerts);

  if (maxPctDelta < MIN_PCT_DELTA) {
    const explanation = html`
      The largest regression is smaller than
      ${tr.b.Unit.byName.normalizedPercentage.format(MIN_PCT_DELTA)}.
    `;
    return {bugId: ExistingBugRequest.IGNORE_BUG_ID, explanation};
  }

  if (bugId) {
    const explanation = html`
      ${maxAlertCount} similar alert${plural(maxAlertCount)} were assigned to
      <a href="${crbug(bugId)}" target="_blank">${bugId}</a>.
    `;
    return {bugId, explanation};
  }

  const explanation = html`
    A ${tr.b.Unit.byName.normalizedPercentage.format(maxPctDelta)} regression is
    significant with no similar triaged alerts.
  `;
  return {bugId, explanation};
}
