/* Copyright 2018 The Chromium Authors. All rights reserved.
   Use of this source code is governed by a BSD-style license that can be
   found in the LICENSE file.
*/
'use strict';

import '@polymer/polymer/lib/elements/dom-if.js';
import '@polymer/polymer/lib/elements/dom-repeat.js';
import * as PolymerAsync from '@polymer/polymer/lib/utils/async.js';
import ElementBase from './element-base.js';
import {UPDATE} from './simple-redux.js';
import {html} from '@polymer/polymer/polymer-element.js';

import {GestureEventListeners} from
  '@polymer/polymer/lib/mixins/gesture-event-listeners.js';

import {
  animationFrame,
  buildProperties,
  buildState,
  hasCtrlKey,
  measureElement,
} from './utils.js';


export default class ChartBase extends GestureEventListeners(ElementBase) {
  static get is() { return 'chart-base'; }

  static get template() {
    const template = html`
      <style>
        :host {
          display: flex;
        }

        #right {
          display: flex;
          flex-direction: column;
          flex-grow: 1;
        }

        #brush_handles {
          position: relative;
          height: 15px;
        }

        .brush_handle {
          cursor: ew-resize;
          position: absolute;
          top: 0;
        }

        .brush_handle path {
          fill: rgba(0, 0, 0, 0.3);
        }

        path {
          vector-effect: non-scaling-stroke;
        }

        rect {
          opacity: 0.05;
        }

        #yaxis {
          margin-right: 3px;
        }

        #xaxis {
          margin-top: 3px;
        }

        #xaxis, #yaxis {
          user-select: none;
        }

        line {
          stroke-width: 1;
          stroke: #ccc;
        }

        #main {
          --mouse: outside;
          position: relative;
        }

        #main:hover {
          --mouse: inside;
        }

        #tooltip {
          display: flex;
          position: absolute;
          white-space: pre;
          z-index: var(--layer-menu, 100);
        }

        #tooltip[hidden] {
          display: none;
        }

        #tooltip table {
          background-color: var(--background-color, white);
          border-style: solid;
          border-width: 2px;
        }

        #tooltip td {
          vertical-align: text-top;
        }

        .icon {
          /* UA stylesheet sets overflow:hidden for foreignObject, so prevent
            overflow.
          */
          height: 100%;
          transform: translate(-12px, -12px);
          width: 100%;
        }

        .icon iron-icon {
          position: static;
        }
      </style>

      <svg
          id="yaxis"
          width$="[[yAxis.width]]"
          height$="[[graphHeight]]"
          style$="margin-top: [[brushPointSize_(brushSize)]]px;
                  margin-bottom: [[xAxis.height]]px;">
        <template is="dom-repeat" items="[[yAxis.ticks]]" as="tick">
          <text
              x$="[[yAxis.width]]"
              y$="[[tick.yPct]]"
              text-anchor="end"
              alignment-baseline$="[[tickAnchor_(tick)]]">
            [[tick.text]]
          </text>
        </template>
      </svg>

      <div id="right">
        <div id="brush_handles">
          <template is="dom-repeat" items="[[xAxis.brushes]]" as="brush"
              index-as="brushIndex">
            <div class="brush_handle"
                on-track="onTrackBrushHandle_"
                style$="left: calc([[brush.xPct]] - 5px);">
              <svg
                  height$="[[brushPointSize_(brushSize)]]"
                  width$="[[brushSize]]"
                  viewBox="0 0 2 3">
                <path d="M0,0 L2,0 L2,2 L1,3 L0,2">
                </path>
              </svg>
            </div>
          </template>
        </div>

        <div id="main"
            on-mousemove="onMouseMoveMain_">
          <svg
              width="100%"
              height$="[[graphHeight]]"
              preserveAspectRatio="none"
              on-click="onMainClick_">
            <template is="dom-if" if="[[yAxis.showTickLines]]">
              <template is="dom-repeat" items="[[yAxis.ticks]]" as="tick">
                <line
                    x1="0"
                    x2="100%"
                    y1$="[[tick.yPct]]"
                    y2$="[[tick.yPct]]">
                </line>
              </template>
            </template>

            <template is="dom-if" if="[[hasCursor_(yAxis)]]">
              <line
                  x1="0"
                  x2="100%"
                  y1$="[[yAxis.cursor.pct]]"
                  y2$="[[yAxis.cursor.pct]]"
                  style$="stroke: [[yAxis.cursor.color]];">
              </line>
            </template>

            <template is="dom-if" if="[[xAxis.showTickLines]]">
              <template is="dom-repeat" items="[[xAxis.ticks]]" as="tick">
                <line
                    x1$="[[tick.xPct]]"
                    x2$="[[tick.xPct]]"
                    y1="0"
                    y2="100%">
                </line>
              </template>
            </template>

            <template is="dom-if" if="[[hasCursor_(xAxis)]]">
              <line
                  x1$="[[xAxis.cursor.pct]]"
                  x2$="[[xAxis.cursor.pct]]"
                  y1="0"
                  y2="100%"
                  style$="stroke: [[xAxis.cursor.color]];">
              </line>
            </template>

            <template is="dom-repeat" items="[[antiBrushes_(xAxis.brushes)]]"
                as="antiBrush">
              <rect
                  x$="[[antiBrush.start]]"
                  y="0"
                  width$="[[antiBrush.length]]"
                  height="100%">
              </rect>
            </template>

            <template is="dom-repeat" items="[[lines]]" as="line">
              <svg
                  viewBox="0 0 100 100"
                  x="0"
                  y="0"
                  width="100%"
                  height="100%"
                  preserveAspectRatio="none">
                <path
                    d$="[[line.path]]"
                    stroke$="[[line.color]]"
                    stroke-width$="[[line.strokeWidth]]"
                    fill="none">
                </path>
                <template is="dom-if" if="[[line.shadePoints]]">
                  <polygon
                      points$="[[line.shadePoints]]"
                      fill$="[[line.shadeFill]]"
                      stroke="0">
                  </polygon>
                </template>
              </svg>

              <template is="dom-repeat" items="[[collectIcons_(line)]]"
                  as="datum">
                <foreignObject
                    x$="[[pct_(datum.xPct)]]"
                    y$="[[pct_(datum.yPct)]]"
                    class="icon">
                  <body xmlns="http://www.w3.org/1999/xhtml">
                    <iron-icon
                        icon="[[datum.icon]]"
                        style$="color: [[datum.iconColor]]">
                    </iron-icon>
                  </body>
                </foreignObject>
              </template>
            </template>
          </svg>

          <div id="tooltip"
              hidden$="[[tooltipHidden_(tooltip)]]"
              style$="left: [[tooltip.left]]; right: [[tooltip.right]];
                      top: [[tooltip.top]]; bottom: [[tooltip.bottom]];">
            <table style$="border-color: [[tooltip.color]];">
              <template is="dom-repeat" items="[[tooltip.rows]]" as="row">
                <tr style$="color: [[row.color]]">
                  <td colspan$="[[row.colspan]]">[[row.name]]</td>
                  <template is="dom-if" if="[[!isEqual_(row.colspan, 2)]]">
                    <td>[[row.value]]</td>
                  </template>
                </tr>
              </template>
            </table>
          </div>
        </div>

        <svg
            id="xaxis"
            width="100%"
            height$="[[xAxis.height]]">
          <template is="dom-repeat" items="[[xAxis.ticks]]" as="tick">
            <text
                x$="[[tick.xPct]]"
                y="100%"
                text-anchor$="[[tickAnchor_(tick)]]"
                alignment-baseline="after-edge">
              [[tick.text]]
            </text>
          </template>
        </svg>
      </div>
    `;
    PolymerSvgTemplate(template.content, document);
    return template;
  }

  collectIcons_(line) {
    if (!line || !line.data) return [];
    return line.data.filter(datum => datum.icon);
  }

  hasCursor_(axis) {
    return axis && axis.cursor && axis.cursor.pct;
  }

  antiBrushes_(brushes) {
    return ChartBase.antiBrushes(brushes);
  }

  pct_(x) {
    return x + '%';
  }

  brushPointSize_(brushSize) {
    if (Number.isNaN(brushSize)) return 0;
    return brushSize * 1.5;
  }

  tickAnchor_(tick) {
    return tick.anchor || 'middle';
  }

  onMainClick_(event) {
    this.dispatchEvent(new CustomEvent('chart-click', {
      bubbles: true,
      composed: true,
      detail: {
        ctrlKey: hasCtrlKey(event),
        nearestLine: this.previousNearestLine,
        nearestPoint: this.previousNearestPoint,
      },
    }));
  }

  tooltipHidden_(tooltip) {
    return !tooltip || !tooltip.isVisible || this.isEmpty_(tooltip.rows);
  }

  get isMouseOverMain() {
    return getComputedStyle(this.$.main).getPropertyValue(
        '--mouse').includes('inside');
  }

  async maybePollMouseLeaveMain_() {
    if (this.mouseLeaveMainPoller_) return;

    this.mouseLeaveMainPoller_ = this.pollMouseLeaveMain_();
    await this.mouseLeaveMainPoller_;
    this.mouseLeaveMainPoller_ = undefined;
    this.previousNearestPoint = undefined;
    this.previousNearestLine = undefined;
    this.dispatchEvent(new CustomEvent('mouse-leave-main', {
      bubbles: true,
      composed: true,
    }));
  }

  async pollMouseLeaveMain_() {
    // Ideally, an on-mouseleave listener would dispatchEvent so that callers
    // could hide the tooltip and whatever else when the mouse leaves the main
    // area. However, mouseleave and mouseout are flaky in obnoxious ways. CSS
    // :hover seems to be robust, so a :hover selector sets the property
    // --mouse: inside. mouseLeaveMain_ polls this property.
    while (this.isMouseOverMain) {
      await animationFrame();
    }
  }

  async onTrackBrushHandle_(event) {
    const xPct = ChartBase.computeBrush(
        event.detail.x, await measureElement(this.$.main));
    this.dispatch('brushX', this.statePath, event.model.brushIndex, xPct);
    this.dispatchEvent(new CustomEvent('brush', {
      bubbles: true,
      composed: true,
      detail: {
        brushIndex: event.model.brushIndex,
        sourceEvent: event,
      },
    }));
  }

  async onMouseMoveMain_(event) {
    if (!this.showTooltip) return;

    // It might be expensive to measure $.main and getNearestPoint, so
    // debounce to save CPU.
    this.debounce('mousemove-main', async() => {
      const mainRect = await measureElement(this.$.main);
      const {nearestPoint, nearestLine} = ChartBase.getNearestPoint(
          event, mainRect, this.lines);
      if (!nearestPoint) return;

      // If the mouse left main in between onMouseMoveMain_() and now, don't
      // re-display tooltip.
      if (!this.isMouseOverMain) return;

      // It might be expensive to build and render the tooltip, so only
      // dispatch get-tooltip when the nearestPoint changes.
      if (nearestPoint === this.previousNearestPoint) return;
      this.previousNearestPoint = nearestPoint;
      this.previousNearestLine = nearestLine;

      this.dispatchEvent(new CustomEvent('get-tooltip', {
        bubbles: true,
        composed: true,
        detail: {mainRect, nearestPoint, nearestLine},
      }));
      this.maybePollMouseLeaveMain_();
    }, PolymerAsync.animationFrame);
  }
}

ChartBase.State = {
  brushSize: options => options.brushSize || 10,
  graphHeight: options => options.graphHeight || 200,
  lines: options => options.lines || [],
  showTooltip: options => options.showTooltip || false,
  tooltip: options => {
    return {
      isVisible: false,
      left: '',
      right: '',
      top: '',
      bottom: '',
      color: '',
      rows: [],
      ...options.tooltip,
    };
  },
  xAxis: options => {
    return {
      brushes: [],
      height: 0,
      range: new tr.b.math.Range(),
      showTickLines: false,
      ticks: [],
      ...options.xAxis,
    };
  },
  yAxis: options => {
    return {
      brushes: [],
      range: new tr.b.math.Range(),
      showTickLines: false,
      ticks: [],
      width: 0,
      ...options.yAxis,
    };
  },
};

ChartBase.properties = buildProperties('state', ChartBase.State);
ChartBase.buildState = options => buildState(ChartBase.State, options);

ChartBase.actions = {
  brushX: (statePath, brushIndex, xPct) => async(dispatch, getState) => {
    const path = `${statePath}.xAxis.brushes.${brushIndex}`;
    dispatch(UPDATE(path, {xPct}));
  },
};

ChartBase.reducers = {
  boldLine: (state, {lineIndex}, rootState) => {
    const lines = state.lines.map((line, index) => {
      const strokeWidth = (index === lineIndex) ? 2 : 1;
      return {...line, strokeWidth};
    });
    if (lineIndex !== undefined && lineIndex !== (lines.length - 1)) {
      // Move lineIndex to the end so it is drawn over top of any other
      // lines.
      [lines[lineIndex], lines[lines.length - 1]] =
        [lines[lines.length - 1], lines[lineIndex]];
    }
    return {...state, lines};
  },
};

ChartBase.antiBrushes = brushes => {
  if (!brushes || brushes.length === 0) return [];
  if (brushes.length % 2 === 1) throw new Error('Odd number of brushes');
  brushes = brushes.map(brush =>
    Number.parseFloat(brush.xPct)).sort((a, b) => a - b);
  let previous = {start: 0, length: undefined};
  const antiBrushes = [previous];
  for (let i = 0; i < brushes.length; i += 2) {
    if (previous.start === 0 && brushes[i] === 0) {
      antiBrushes.splice(0, 1);
    } else {
      previous.length = (brushes[i] - previous.start) + '%';
      previous.start += '%';
    }
    if (brushes[i + 1] === 100) return antiBrushes;
    previous = {start: brushes[i + 1], length: undefined};
    antiBrushes.push(previous);
  }
  previous.length = (100 - previous.start) + '%';
  previous.start += '%';
  return antiBrushes;
};

ChartBase.computeBrush = (x, containerRect) => {
  const value = tr.b.math.normalize(
      x, containerRect.left, containerRect.right);
  return tr.b.math.clamp(100 * value, 0, 100) + '%';
};

ChartBase.getNearestPoint = (pt, rect, lines) => {
  if (!lines) return {};
  const xPct = tr.b.math.normalize(pt.x, rect.left, rect.right) * 100;
  const yPct = tr.b.math.normalize(pt.y, rect.top, rect.bottom) * 100;
  let nearestPoint;
  let nearestDelta;
  let nearestLine;
  for (const line of lines) {
    const datum = tr.b.findClosestElementInSortedArray(
        line.data, d => d.xPct, xPct, 10);
    if (datum === null) continue;
    const dx = xPct - datum.xPct;
    const dy = yPct - datum.yPct;
    const delta = Math.sqrt(dx * dx + dy * dy);
    if (nearestPoint && (nearestDelta < delta)) {
      continue;
    }
    nearestPoint = datum;
    nearestDelta = delta;
    nearestLine = line;
  }
  return {nearestPoint, nearestLine};
};

ElementBase.register(ChartBase);
