// Copyright (c) 2012 The Chromium Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

'use strict';

// Populated by constants from the browser.  Used only by this file.
var NetInfoSources = null;

/**
 * This class provides a "bridge" for communicating between the javascript and
 * the browser.
 */
var BrowserBridge = (function() {
  /**
   * Delay in milliseconds between updates of certain browser information.
   */
  var POLL_INTERVAL_MS = 5000;

  /**
   * @constructor
   */
  function BrowserBridge() {
    assertFirstConstructorCall(BrowserBridge);

    // List of observers for various bits of browser state.
    this.constantsObservers_ = [];

    this.pollableDataHelpers_ = {};

    // Add PollableDataHelpers for NetInfoSources, which retrieve information
    // directly from the network stack.
    this.addNetInfoPollableDataHelper(
        'proxySettings', 'onProxySettingsChanged');
    this.addNetInfoPollableDataHelper('badProxies', 'onBadProxiesChanged');
    this.addNetInfoPollableDataHelper(
        'hostResolverInfo', 'onHostResolverInfoChanged');
    this.addNetInfoPollableDataHelper(
        'socketPoolInfo', 'onSocketPoolInfoChanged');
    this.addNetInfoPollableDataHelper(
        'spdySessionInfo', 'onSpdySessionInfoChanged');
    this.addNetInfoPollableDataHelper('spdyStatus', 'onSpdyStatusChanged');
    this.addNetInfoPollableDataHelper(
        'altSvcMappings', 'onAltSvcMappingsChanged');
    this.addNetInfoPollableDataHelper('quicInfo', 'onQuicInfoChanged');
    this.addNetInfoPollableDataHelper(
        'reportingInfo', 'onReportingInfoChanged');
    this.addNetInfoPollableDataHelper(
        'httpCacheInfo', 'onHttpCacheInfoChanged');

    // Add other PollableDataHelpers.
    if (cr.isWindows) {
      this.pollableDataHelpers_.serviceProviders = new PollableDataHelper(
          'onServiceProvidersChanged');
    }
    this.pollableDataHelpers_.prerenderInfo = new PollableDataHelper(
        'onPrerenderInfoChanged');
    this.pollableDataHelpers_.extensionInfo = new PollableDataHelper(
        'onExtensionInfoChanged');
    this.pollableDataHelpers_.dataReductionProxyInfo = new PollableDataHelper(
        'onDataReductionProxyInfoChanged');

    // Interval id returned by window.setInterval for polling timer.
    this.pollIntervalId_ = null;
  }

  cr.addSingletonGetter(BrowserBridge);

  BrowserBridge.prototype = {

    //--------------------------------------------------------------------------
    // Messages received from the browser.
    //--------------------------------------------------------------------------

    receivedConstants: function(constants) {
      NetInfoSources = constants.netInfoSources;
      for (var i = 0; i < this.constantsObservers_.length; i++)
        this.constantsObservers_[i].onReceivedConstants(constants);
    },

    receivedLogEntries: function(logEntries) {
      EventsTracker.getInstance().addLogEntries(logEntries);
    },

    receivedNetInfo: function(netInfo) {
      // Dispatch |netInfo| to the various PollableDataHelpers listening to
      // each field it contains.
      //
      // Currently information is only received from one source at a time, but
      // the API does allow for data from more that one to be requested at once.
      for (var source in netInfo)
        this.pollableDataHelpers_[source].update(netInfo[source]);
    },

    receivedServiceProviders: function(serviceProviders) {
      this.pollableDataHelpers_.serviceProviders.update(serviceProviders);
    },

    receivedPrerenderInfo: function(prerenderInfo) {
      this.pollableDataHelpers_.prerenderInfo.update(prerenderInfo);
    },

    receivedExtensionInfo: function(extensionInfo) {
      this.pollableDataHelpers_.extensionInfo.update(extensionInfo);
    },

    receivedDataReductionProxyInfo: function(dataReductionProxyInfo) {
      this.pollableDataHelpers_.dataReductionProxyInfo.update(
          dataReductionProxyInfo);
    },

    //--------------------------------------------------------------------------

    /**
     * Adds a listener of the proxy settings. |observer| will be called back
     * when data is received, through:
     *
     *   observer.onProxySettingsChanged(proxySettings)
     *
     * |proxySettings| is a dictionary with (up to) two properties:
     *
     *   "original"  -- The settings that chrome was configured to use
     *                  (i.e. system settings.)
     *   "effective" -- The "effective" proxy settings that chrome is using.
     *                  (decides between the manual/automatic modes of the
     *                  fetched settings).
     *
     * Each of these two configurations is formatted as a string, and may be
     * omitted if not yet initialized.
     *
     * If |ignoreWhenUnchanged| is true, data is only sent when it changes.
     * If it's false, data is sent whenever it's received from the browser.
     */
    addProxySettingsObserver: function(observer, ignoreWhenUnchanged) {
      this.pollableDataHelpers_.proxySettings.addObserver(
          observer, ignoreWhenUnchanged);
    },

    /**
     * Adds a listener of the proxy settings. |observer| will be called back
     * when data is received, through:
     *
     *   observer.onBadProxiesChanged(badProxies)
     *
     * |badProxies| is an array, where each entry has the property:
     *   badProxies[i].proxy_uri: String identify the proxy.
     *   badProxies[i].bad_until: The time when the proxy stops being considered
     *                            bad. Note the time is in time ticks.
     */
    addBadProxiesObserver: function(observer, ignoreWhenUnchanged) {
      this.pollableDataHelpers_.badProxies.addObserver(
          observer, ignoreWhenUnchanged);
    },

    /**
     * Adds a listener of the host resolver info. |observer| will be called back
     * when data is received, through:
     *
     *   observer.onHostResolverInfoChanged(hostResolverInfo)
     */
    addHostResolverInfoObserver: function(observer, ignoreWhenUnchanged) {
      this.pollableDataHelpers_.hostResolverInfo.addObserver(
          observer, ignoreWhenUnchanged);
    },

    /**
     * Adds a listener of the socket pool. |observer| will be called back
     * when data is received, through:
     *
     *   observer.onSocketPoolInfoChanged(socketPoolInfo)
     */
    addSocketPoolInfoObserver: function(observer, ignoreWhenUnchanged) {
      this.pollableDataHelpers_.socketPoolInfo.addObserver(
          observer, ignoreWhenUnchanged);
    },

    /**
     * Adds a listener of the QUIC info. |observer| will be called back
     * when data is received, through:
     *
     *   observer.onQuicInfoChanged(quicInfo)
     */
    addQuicInfoObserver: function(observer, ignoreWhenUnchanged) {
      this.pollableDataHelpers_.quicInfo.addObserver(
          observer, ignoreWhenUnchanged);
    },

    /**
     * Adds a listener of the Reporting info. |observer| will be called back
     * when data is received, through:
     *
     *   observer.onReportingInfoChanged(reportingInfo)
     */
    addReportingInfoObserver: function(observer, ignoreWhenUnchanged) {
      this.pollableDataHelpers_.reportingInfo.addObserver(
          observer, ignoreWhenUnchanged);
    },

    /**
     * Adds a listener of the SPDY info. |observer| will be called back
     * when data is received, through:
     *
     *   observer.onSpdySessionInfoChanged(spdySessionInfo)
     */
    addSpdySessionInfoObserver: function(observer, ignoreWhenUnchanged) {
      this.pollableDataHelpers_.spdySessionInfo.addObserver(
          observer, ignoreWhenUnchanged);
    },

    /**
     * Adds a listener of the SPDY status. |observer| will be called back
     * when data is received, through:
     *
     *   observer.onSpdyStatusChanged(spdyStatus)
     */
    addSpdyStatusObserver: function(observer, ignoreWhenUnchanged) {
      this.pollableDataHelpers_.spdyStatus.addObserver(
          observer, ignoreWhenUnchanged);
    },

    /**
     * Adds a listener of the altSvcMappings. |observer| will be
     * called back when data is received, through:
     *
     *   observer.onAltSvcMappingsChanged(altSvcMappings)
     */
    addAltSvcMappingsObserver: function(observer, ignoreWhenUnchanged) {
      this.pollableDataHelpers_.altSvcMappings.addObserver(
          observer, ignoreWhenUnchanged);
    },

    /**
     * Adds a listener of the service providers info. |observer| will be called
     * back when data is received, through:
     *
     *   observer.onServiceProvidersChanged(serviceProviders)
     *
     * Will do nothing if on a platform other than Windows, as service providers
     * are only present on Windows.
     */
    addServiceProvidersObserver: function(observer, ignoreWhenUnchanged) {
      if (this.pollableDataHelpers_.serviceProviders) {
        this.pollableDataHelpers_.serviceProviders.addObserver(
            observer, ignoreWhenUnchanged);
      }
    },

    /**
     * Adds a listener for the http cache info results.
     * The observer will be called back with:
     *
     *   observer.onHttpCacheInfoChanged(info);
     */
    addHttpCacheInfoObserver: function(observer, ignoreWhenUnchanged) {
      this.pollableDataHelpers_.httpCacheInfo.addObserver(
          observer, ignoreWhenUnchanged);
    },

    /**
     * Adds a listener for the received constants event. |observer| will be
     * called back when the constants are received, through:
     *
     *   observer.onReceivedConstants(constants);
     */
    addConstantsObserver: function(observer) {
      this.constantsObservers_.push(observer);
    },

    /**
     * Adds a listener for updated prerender info events
     * |observer| will be called back with:
     *
     *   observer.onPrerenderInfoChanged(prerenderInfo);
     */
    addPrerenderInfoObserver: function(observer, ignoreWhenUnchanged) {
      this.pollableDataHelpers_.prerenderInfo.addObserver(
          observer, ignoreWhenUnchanged);
    },

    /**
     * Adds a listener of extension information. |observer| will be called
     * back when data is received, through:
     *
     *   observer.onExtensionInfoChanged(extensionInfo)
     */
    addExtensionInfoObserver: function(observer, ignoreWhenUnchanged) {
      this.pollableDataHelpers_.extensionInfo.addObserver(
          observer, ignoreWhenUnchanged);
    },

    /**
     * Adds a PollableDataHelper that listens to the specified NetInfoSource.
     */
    addNetInfoPollableDataHelper: function(sourceName, observerMethodName) {
      this.pollableDataHelpers_[sourceName] = new PollableDataHelper(
          observerMethodName);
    },
  };

  /**
   * This is a helper class used by BrowserBridge, to keep track of:
   *   - the list of observers interested in some piece of data.
   *   - the last known value of that piece of data.
   *   - the name of the callback method to invoke on observers.
   *   - the update function.
   * @constructor
   */
  function PollableDataHelper(observerMethodName) {
    this.observerMethodName_ = observerMethodName;
    this.observerInfos_ = [];
  }

  PollableDataHelper.prototype = {
    getObserverMethodName: function() {
      return this.observerMethodName_;
    },

    isObserver: function(object) {
      for (var i = 0; i < this.observerInfos_.length; i++) {
        if (this.observerInfos_[i].observer === object)
          return true;
      }
      return false;
    },

    /**
     * If |ignoreWhenUnchanged| is true, we won't send data again until it
     * changes.
     */
    addObserver: function(observer, ignoreWhenUnchanged) {
      this.observerInfos_.push(new ObserverInfo(observer, ignoreWhenUnchanged));
    },

    removeObserver: function(observer) {
      for (var i = 0; i < this.observerInfos_.length; i++) {
        if (this.observerInfos_[i].observer === observer) {
          this.observerInfos_.splice(i, 1);
          return;
        }
      }
    },

    /**
     * Helper function to handle calling all the observers, but ONLY if the data
     * has actually changed since last time or the observer has yet to receive
     * any data. This is used for data we received from browser on an update
     * loop.
     */
    update: function(data) {
      var prevData = this.currentData_;
      var changed = false;

      // If the data hasn't changed since last time, will only need to notify
      // observers that have not yet received any data.
      if (!prevData || JSON.stringify(prevData) != JSON.stringify(data)) {
        changed = true;
        this.currentData_ = data;
      }

      // Notify the observers of the change, as needed.
      for (var i = 0; i < this.observerInfos_.length; i++) {
        var observerInfo = this.observerInfos_[i];
        if (changed || !observerInfo.hasReceivedData ||
            !observerInfo.ignoreWhenUnchanged) {
          observerInfo.observer[this.observerMethodName_](this.currentData_);
          observerInfo.hasReceivedData = true;
        }
      }
    },

    /**
     * Returns true if one of the observers actively wants the data
     * (i.e. is visible).
     */
    hasActiveObserver: function() {
      for (var i = 0; i < this.observerInfos_.length; i++) {
        if (this.observerInfos_[i].observer.isActive())
          return true;
      }
      return false;
    }
  };

  /**
   * This is a helper class used by PollableDataHelper, to keep track of
   * each observer and whether or not it has received any data.  The
   * latter is used to make sure that new observers get sent data on the
   * update following their creation.
   * @constructor
   */
  function ObserverInfo(observer, ignoreWhenUnchanged) {
    this.observer = observer;
    this.hasReceivedData = false;
    this.ignoreWhenUnchanged = ignoreWhenUnchanged;
  }

  return BrowserBridge;
})();

