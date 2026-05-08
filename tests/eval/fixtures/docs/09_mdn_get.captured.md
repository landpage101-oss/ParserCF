- [Skip to main content](https://developer.mozilla.org/en-US/docs/Web/HTTP/Reference/Methods/GET#content)
- [Skip to search](https://developer.mozilla.org/en-US/docs/Web/HTTP/Reference/Methods/GET#search)

Learn frontend, backend, and AI from our course partner
[Scrimba](https://scrimba.com/learn/frontend?via=mdn)

# GET request method


Baseline

Widely available


This feature is well established and works across many devices and browser versions. It’s been available across browsers since July 2015.

- [Learn more](https://developer.mozilla.org/en-US/docs/Glossary/Baseline/Compatibility)
- [See full compatibility](https://developer.mozilla.org/en-US/docs/Web/HTTP/Reference/Methods/GET#browser_compatibility)
- [Report feedback](https://survey.alchemer.com/s3/7634825/MDN-baseline-feedback?page=%2Fen-US%2Fdocs%2FWeb%2FHTTP%2FReference%2FMethods%2FGET&level=high)

The **`GET`** HTTP method requests a representation of the specified resource.
Requests using `GET` should only be used to request data and shouldn't contain a body.

**Note:**
The semantics of sending a message body in `GET` requests are undefined.
Some servers may reject the request with a [4XX client error](https://developer.mozilla.org/en-US/docs/Web/HTTP/Reference/Status#client_error_responses) response.

| Request has body | No |
| Successful response has body | Yes |
| [Safe](https://developer.mozilla.org/en-US/docs/Glossary/Safe/HTTP) | Yes |
| [Idempotent](https://developer.mozilla.org/en-US/docs/Glossary/Idempotent) | Yes |
| [Cacheable](https://developer.mozilla.org/en-US/docs/Glossary/Cacheable) | Yes |
| Allowed in HTML forms | Yes |

## [Syntax](https://developer.mozilla.org/en-US/docs/Web/HTTP/Reference/Methods/GET\#syntax)

httpCopy

```
GET <request-target>["?"<query>] HTTP/1.1
```

[`<request-target>`](https://developer.mozilla.org/en-US/docs/Web/HTTP/Reference/Methods/GET#request-target)

Identifies the target resource of the request when combined with the information provided in the [`Host`](https://developer.mozilla.org/en-US/docs/Web/HTTP/Reference/Headers/Host) header.
This is an absolute path (e.g., `/path/to/file.html`) in requests to an origin server, and an absolute URL in requests to proxies (e.g., `http://www.example.com/path/to/file.html`).

[`<query>`Optional](https://developer.mozilla.org/en-US/docs/Web/HTTP/Reference/Methods/GET#query)

An optional query component preceded by a question-mark `?`.
Often used to carry identifying information in the form of `key=value` pairs.

## [Examples](https://developer.mozilla.org/en-US/docs/Web/HTTP/Reference/Methods/GET\#examples)

### [Successfully retrieving a resource](https://developer.mozilla.org/en-US/docs/Web/HTTP/Reference/Methods/GET\#successfully_retrieving_a_resource)

The following `GET` request asks for the resource at `example.com/contact`:

httpCopy

```
GET /contact HTTP/1.1
```

The server sends back the resource with a [`200 OK`](https://developer.mozilla.org/en-US/docs/Web/HTTP/Reference/Status/200) status code, indicating success:

httpCopy

```
HTTP/1.1 200 OK

<!doctype html>
<!-- HTML content follows -->
```

## [Specifications](https://developer.mozilla.org/en-US/docs/Web/HTTP/Reference/Methods/GET\#specifications)

| Specification |
| --- |
| [HTTP Semantics\<br>\# GET](https://httpwg.org/specs/rfc9110.html#GET) |

## [Browser compatibility](https://developer.mozilla.org/en-US/docs/Web/HTTP/Reference/Methods/GET\#browser_compatibility)

[Report problems with this compatibility data](https://developer.mozilla.org/en-US/docs/Web/HTTP/Reference/Methods/GET# "Report an issue with this compatibility data") •
[View data on GitHub](https://github.com/mdn/browser-compat-data/tree/main/http/methods.json "File: http/methods.json")

|  | desktop | mobile |
| --- | --- | --- |
|  | Chrome | Edge | Firefox | Opera | Safari | Chrome Android | Firefox for Android | Opera Android | Safari on iOS | Samsung Internet | WebView Android | WebView on iOS |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| `GET` | Chrome – Full support<br>Chrome1 | Edge – Full support<br>Edge12 | Firefox – Full support<br>Firefox1 | Opera – Full support<br>Opera2 | Safari – Full support<br>Safari1 | Chrome Android – Full support<br>Chrome Android18 | Firefox for Android – Full support<br>Firefox for Android4 | Opera Android – Full support<br>Opera Android10.1 | Safari on iOS – Full support<br>Safari on iOS1 | Samsung Internet – Full support<br>Samsung Internet1 | WebView Android – Full support<br>WebView Android1 | WebView on iOS – Full support<br>WebView on iOS1 |

### Legend

Tip: you can click/tap on a cell for more information.


Full supportFull support

## [See also](https://developer.mozilla.org/en-US/docs/Web/HTTP/Reference/Methods/GET\#see_also)

- [HTTP request methods](https://developer.mozilla.org/en-US/docs/Web/HTTP/Reference/Methods)
- [HTTP response status codes](https://developer.mozilla.org/en-US/docs/Web/HTTP/Reference/Status)
- [HTTP headers](https://developer.mozilla.org/en-US/docs/Web/HTTP/Reference/Headers)
- [`Range`](https://developer.mozilla.org/en-US/docs/Web/HTTP/Reference/Headers/Range) header
- [`POST`](https://developer.mozilla.org/en-US/docs/Web/HTTP/Reference/Methods/POST) method

## Help improve MDN

Was this page helpful to you?

YesNo

[Learn how to contribute](https://developer.mozilla.org/en-US/docs/MDN/Community/Getting_started)

This page was last modified on Jul 4, 2025 by [MDN contributors](https://developer.mozilla.org/en-US/docs/Web/HTTP/Reference/Methods/GET/contributors.txt).


[View this page on GitHub](https://github.com/mdn/content/blob/main/files/en-us/web/http/reference/methods/get/index.md?plain=1 "Folder: en-us/web/http/reference/methods/get (Opens in a new tab)") • [Report a problem with this content](https://github.com/mdn/content/issues/new?template=page-report.yml&mdn-url=https%3A%2F%2Fdeveloper.mozilla.org%2Fen-US%2Fdocs%2FWeb%2FHTTP%2FReference%2FMethods%2FGET&metadata=%3C%21--+Do+not+make+changes+below+this+line+--%3E%0A%3Cdetails%3E%0A%3Csummary%3EPage+report+details%3C%2Fsummary%3E%0A%0A*+Folder%3A+%60en-us%2Fweb%2Fhttp%2Freference%2Fmethods%2Fget%60%0A*+MDN+URL%3A+https%3A%2F%2Fdeveloper.mozilla.org%2Fen-US%2Fdocs%2FWeb%2FHTTP%2FReference%2FMethods%2FGET%0A*+GitHub+URL%3A+https%3A%2F%2Fgithub.com%2Fmdn%2Fcontent%2Fblob%2Fmain%2Ffiles%2Fen-us%2Fweb%2Fhttp%2Freference%2Fmethods%2Fget%2Findex.md%0A*+Last+commit%3A+https%3A%2F%2Fgithub.com%2Fmdn%2Fcontent%2Fcommit%2Fad5b5e31f81795d692e66dadb7818ba8b220ad15%0A*+Document+last+modified%3A+2025-07-04T01%3A10%3A07.000Z%0A%0A%3C%2Fdetails%3E "This will take you to GitHub to file a new issue.")
