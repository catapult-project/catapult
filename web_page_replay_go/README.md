# Web Page Replay
Web Page Replay (WprGo) is a performance testing tool written in Golang for
recording and replaying web pages. WprGo is currently used in Telemetry for
Chrome benchmarking purposes. This requires go 1.8 and above. This has not been
tested with earlier versions of go. It is supported on Windows, MacOS and Linux.

## Required packages

```
go get github.com/codegangsta/cli
```
## Set up GOPATH
```
export GOPATH=/path/to/web_page_replay_go:"$HOME/go"
```

## Sample usage

### Record mode
* Terminal 1:

  Start wpr in record mode.

  ```
  go run src/wpr.go record --http_port=8080 --https_port=8081 /tmp/archive.wprgo
  ```
  ...

  Ctrl-C

* Terminal 2:

  ```
  google-chrome-beta --user-data-dir=$foo \
   --host-resolver-rules="MAP *:80 127.0.0.1:8080,MAP *:443 127.0.0.1:8081,EXCLUDE localhost"
  ```
  ... wait for record servers to start

### Replay mode
* Terminal 1:

  Start wpr in replay mode.
  ```
  go run src/wpr.go replay --http_port=8080 --https_port=8081 /tmp/archive.wprgo
  ```

* Terminal 2:
  ```
  google-chrome-beta --user-data-dir=$bar \
   --host-resolver-rules="MAP *:80 127.0.0.1:8080,MAP *:443 127.0.0.1:8081,EXCLUDE localhost"`
  ```
  ... wait for replay servers to start

  load the page

## Running on Android

You will need a Linux host machine and an android device.

* Set up reverse port forwarding

```
adb reverse tcp:8080 tcp:8080
adb reverse tcp:8081 tcp:8081
```

* Set up command line arguments

```
build/android/adb_chrome_public_command_line '--host-resolver-rules="MAP *:80 127.0.0.1:8080,MAP *:443 127.0.0.1:8081,EXCLUDE localhost"'
```

* Run wpr.go as usual on the linux machine

### Installing test root CA

WebPageReplay uses self signed certificates for Https requests. To make Chrome
trust these certificates, you can install a test certificate authority as a
local trust anchor. **Note:** Please do this with care because installing the
test root CA compromises your machine. This is currently only supported on
Linux and Android.

Installing the test CA. Specify a `--android_device_id` if you'd like to install
the root CA on an android device.
```
go run src/wpr.go installroot
```
Uninstall the test CA. Specify a `--android_device_id` if you'd like to remove
the root CA from an android device.

```
go run src/wpr.go removeroot
```

## Other use cases

### Http-to-http2 proxy:

* Terminal 1:
```
go run src/wpr.go replay --https_port=8081 --https_to_http_port=8082 \
  /tmp/archive.wprgo
```

* Terminal 2:
```
google-chrome-beta --user-data-dir=$foo \
  --host-resolver-rules="MAP *:443 127.0.0.1:8081,EXCLUDE localhost" \
  --proxy-server=http=https://127.0.0.1:8082 \
  --trusted-spdy-proxy=127.0.0.1:8082
```

## Inspecting an archive

httparchive.go is a convenient script to inspect a wprgo archive. Use `ls`,`cat`
and `edit`. Options are available to specify request url host (`--host`) and
path (`--full-path`).

E.g.

```
go run src/httparchive.go ls /tmp/archive.wprgo --host=example.com --full-path=/index.html
```

## Running unit tests
Run all tests in a specific file.
```
go test transformer_test.go transformer.go
```

Run all tests in `webpagereplay` module.
```
go test webpagereplay -run ''
```

## Contribute
Please read [contributor's guide][contribute]. We use the Catapult
[issue tracker][tracker] for bugs and features. Once your change is reviewed
and ready for landing, please run `telemetry/bin/update_wpr_go_binary` to update
binaries in Google cloud storage.

## Contact
Please email telemetry@chromium.org.

[contribute]: https://github.com/catapult-project/catapult/blob/master/CONTRIBUTING.md
[tracker]: https://github.com/catapult-project/catapult/issues
