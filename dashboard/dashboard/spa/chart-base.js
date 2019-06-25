/* Copyright 2018 The Chromium Authors. All rights reserved.
   Use of this source code is governed by a BSD-style license that can be
   found in the LICENSE file.
*/
'use strict';

import './cp-icon.js';
import {ElementBase, STORE} from './element-base.js';
import {UPDATE} from './simple-redux.js';
import {animationFrame, hasCtrlKey, measureElement} from './utils.js';
import {get} from 'dot-prop-immutable';
import {html, css, svg} from 'lit-element';

export default class ChartBase extends ElementBase {
  static get is() { return 'chart-base'; }

  static get properties() {
    return {
      statePath: String,
      brushSize: Number,
      graphHeight: Number,
      lines: Array,
      showTooltip: Boolean,
      tooltip: Object,
      xAxis: Object,
      yAxis: Object,
    };
  }

  static buildState(options = {}) {
    return {
      brushSize: options.brushSize || 10,
      graphHeight: options.graphHeight || 200,
      lines: options.lines || [],
      showTooltip: options.showTooltip || false,
      tooltip: {
        isVisible: false,
        left: '',
        right: '',
        top: '',
        bottom: '',
        color: '',
        rows: [],
        ...options.tooltip,
      },
      xAxis: {
        brushes: [],
        height: 0,
        range: new tr.b.math.Range(),
        showTickLines: false,
        ticks: [],
        ...options.xAxis,
      },
      yAxis: {
        brushes: [],
        range: new tr.b.math.Range(),
        showTickLines: false,
        ticks: [],
        width: 0,
        ...options.yAxis,
      },
    };
  }

  static get styles() {
    return css`
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

      .icon cp-icon {
        position: static;
      }
    `;
  }

  render() {
    const brushPointSize = Number.isNaN(this.brushSize) ? 0 :
      (this.brushSize * 1.5);
    const showTooltip = (this.tooltip && this.tooltip.isVisible &&
      this.tooltip.rows && this.tooltip.rows.length);

    return html`
      <svg
          id="yaxis"
          width="${this.yAxis.width}"
          height="${this.graphHeight}"
          style="margin-top: ${brushPointSize}px;
                 margin-bottom: ${this.xAxis.height}px;">
        ${(this.yAxis.ticks || []).map(tick => svg`
          <text
              x="${this.yAxis.width}"
              y="${tick.yPct}"
              text-anchor="end"
              alignment-baseline="${tick.anchor || 'middle'}">
            ${tick.text}
          </text>
        `)}
      </svg>

      <div id="right">
        <div id="brush_handles">
          ${(this.xAxis.brushes || []).map((brush, brushIndex) => html`
            <div class="brush_handle"
                @mousedown="${event => this.onDownBrushHandle_(brushIndex)}"
                style="left: calc(${brush.xPct} - 5px);">
              <svg
                  height="${brushPointSize}"
                  width="${this.brushSize}"
                  viewBox="0 0 2 3">
                <path d="M0,0 L2,0 L2,2 L1,3 L0,2">
                </path>
              </svg>
            </div>
          `)}
        </div>

        <div id="main" @mousemove="${this.onMouseMoveMain_}">
          <svg
              width="100%"
              height="${this.graphHeight}"
              preserveAspectRatio="none"
              @click="${this.onMainClick_}">
            ${!this.yAxis.showTickLines ? '' : this.yAxis.ticks.map(
      tick => svg`
        <line x1="0" x2="100%" y1="${tick.yPct}" y2="${tick.yPct}">
        </line>
      `)}

            ${(!this.yAxis || !this.yAxis.cursor ||
               !this.yAxis.cursor.pct) ? '' : svg`
                <line
                    x1="0"
                    x2="100%"
                    y1="${this.yAxis.cursor.pct}"
                    y2="${this.yAxis.cursor.pct}"
                    style="stroke: ${this.yAxis.cursor.color};">
                </line>
              `}

            ${!this.xAxis.showTickLines ? '' : this.xAxis.ticks.map(
      tick => svg`
        <line x1="${tick.xPct}" x2="${tick.xPct}" y1="0" y2="100%">
        </line>
      `)}

            ${(!this.xAxis || !this.xAxis.cursor ||
               !this.xAxis.cursor.pct) ? '' : svg`
                <line
                    x1="${this.xAxis.cursor.pct}"
                    x2="${this.xAxis.cursor.pct}"
                    y1="0"
                    y2="100%"
                    style="stroke: ${this.xAxis.cursor.color};">
                </line>
              `}

            ${ChartBase.antiBrushes(this.xAxis.brushes).map(antiBrush => svg`
              <rect
                  x="${antiBrush.start}"
                  y="0"
                  width="${antiBrush.length}"
                  height="100%">
              </rect>
            `)}

            ${this.lines.map(line => this.renderLine(line))}
          </svg>

          <div id="tooltip"
              ?hidden="${!showTooltip}"
              style="left: ${this.tooltip ? this.tooltip.left : 0};
                     right: ${this.tooltip ? this.tooltip.right : 0};
                     top: ${this.tooltip ? this.tooltip.top : 0};
                     bottom: ${this.tooltip ? this.tooltip.bottom : 0};">
            <table style="border-color: ${
  this.tooltip ? this.tooltip.color : ''};">
              ${(this.tooltip && this.tooltip.rows || []).map(row => html`
                <tr style="color: ${row.color}">
                  <td colspan="${row.colspan}">${row.name}</td>
                  ${(row.colspan === 2) ? '' : html`
                    <td>${row.value}</td>
                  `}
                </tr>
              `)}
            </table>
          </div>
        </div>

        <svg
            id="xaxis"
            width="100%"
            height="${this.xAxis.height}">
          ${this.xAxis.ticks.map(tick => svg`
            <text
                x="${tick.xPct}"
                y="100%"
                text-anchor="${tick.anchor || 'middle'}"
                alignment-baseline="after-edge">
              ${tick.text}
            </text>
          `)}
        </svg>
      </div>
    `;
  }

  renderLine(line) {
    const icons = (!line || !line.data) ? [] : line.data.filter(datum =>
      datum.icon);
    return html`
      <svg
          viewBox="0 0 100 100"
          x="0"
          y="0"
          width="100%"
          height="100%"
          preserveAspectRatio="none">
        <path
            d="${line.path}"
            stroke="${line.color}"
            stroke-width="${line.strokeWidth}"
            fill="none">
        </path>
        ${!line.shadePoints ? '' : svg`
          <polygon
              points="${line.shadePoints}"
              fill="${line.shadeFill}"
              stroke="0">
          </polygon>
        `}
      </svg>

      ${icons.map(datum => svg`
        <foreignObject
            x="${datum.xPct + '%'}"
            y="${datum.yPct + '%'}"
            class="icon">
          <body xmlns="http://www.w3.org/1999/xhtml">
            <cp-icon
                .icon="${datum.icon}"
                style="color: ${datum.iconColor}">
            </cp-icon>
          </body>
        </foreignObject>
      `)}
    `;
  }

  firstUpdated() {
    this.mainDiv = this.shadowRoot.querySelector('#main');
    this.tooltipDiv = this.shadowRoot.querySelector('#tooltip');
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

  get isMouseOverMain() {
    const mainStyle = getComputedStyle(this.mainDiv);
    return mainStyle.getPropertyValue('--mouse').includes('inside');
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
    // Ideally, an @mouseleave listener would dispatchEvent so that callers
    // could hide the tooltip and whatever else when the mouse leaves the main
    // area. However, mouseleave and mouseout are flaky in obnoxious ways. CSS
    // :hover seems to be robust, so a :hover selector sets the property
    // --mouse: inside. mouseLeaveMain_ polls this property.
    while (this.isMouseOverMain) {
      await animationFrame();
    }
  }

  constructor() {
    super();
    this.onMouseMove_ = this.onMouseMove_.bind(this);
    this.onMouseUp_ = this.onMouseUp_.bind(this);
  }

  onDownBrushHandle_(brushIndex) {
    this.draggingBrushHandle_ = brushIndex;
    this.addEventListener('mousemove', this.onMouseMove_);
    this.addEventListener('mouseup', this.onMouseUp_);
  }

  async onMouseMove_(event) {
    if (event.which !== 1) {
      this.onEndDragBrushHandle_();
      return;
    }

    const xPct = ChartBase.computeBrush(
        event.x, await measureElement(this.mainDiv));
    const brushPath = `${this.statePath}.xAxis.brushes.${
      this.draggingBrushHandle_}`;
    STORE.dispatch(UPDATE(brushPath, {xPct}));
  }

  onEndDragBrushHandle_() {
    this.dispatchEvent(new CustomEvent('brush-end', {
      bubbles: true,
      composed: true,
      detail: {
        brushIndex: this.draggingBrushHandle_,
      },
    }));
    this.draggingBrushHandle_ = undefined;
    this.removeEventListener('mousemove', this.onMouseMove_);
    this.removeEventListener('mouseup', this.onMouseUp_);
  }

  onMouseUp_(event) {
    if (this.draggingBrushHandle_ !== undefined) {
      this.onEndDragBrushHandle_();
    }
  }

  async onMouseMoveMain_(event) {
    if (!this.showTooltip) return;

    // It might be expensive to measure $.main and getNearestPoint, so
    // debounce to save CPU.
    this.debounce('mousemove-main', async() => {
      const mainRect = await measureElement(this.mainDiv);
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
    });
  }
}

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
