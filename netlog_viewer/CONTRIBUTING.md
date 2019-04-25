Running locally
--------------

```
git clone https://chromium.googlesource.com/catapult
cd catapult/netlog_viewer/netlog_viewer
ln -s ../../third_party/polymer/components/
python -m SimpleHTTPServer 8080
```


Note that you can serve the static files using whatever web server you like (doesn't have to be `SimpleHTTPServer`, as there is no server-side dependency beyond static files.)


Running tests
--------------

Startup a dev server to serve the HTML:

```
bin/run_dev_server --no-install-hooks --port 8111
```

Navigate to [http://localhost:8111/netlog_viewer/tests.html](http://localhost:8111/netlog_viewer/tests.html).

Alternately to run the tests in a headless mode from console can use `netlog_viewer/bin/run_dev_server_tests`, however this currently has some problems due to how things have been polymerized.


Reporting bugs
--------------

Please use the [Chromium bug tracker](http://crbug.com/new), and add
`[NetLogViewer]` in the title. If you have edit access, please also set the
component to `Internals>Network>Logging`.


Contributing changes
--------------

Changes should be sumitted using a Gerrit code review, with the reviewer set to one of the [NetLog OWNERS](OWNERS). For instructions on how to use the code review system, see [catapult/CONTRIBUTING.md](../CONTRIBUTING.md).


Known issues
--------------

The viewer code was extracted from Chromium and has not been modernized yet. In particular:
 * Not properly converted to components/Polymer.
 * Uses ancient layout code that could be replaced by modern CSS.
 * Doesn't use modern class notation (some files have been converted by not all).
 * The test infrastructure has glitches due to how it was (not) componentized.
