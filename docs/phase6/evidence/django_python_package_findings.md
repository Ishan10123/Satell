<h2>:mag: Vulnerabilities of <code>django_app-django:latest</code></h2>

<details open="true"><summary>:package: Image Reference</strong> <code>django_app-django:latest</code></summary>
<table>
<tr><td>digest</td><td><code>sha256:e1d5743ea1a4adcc056a3e686f00358f1b3434376d879b43e9428db616df7b13</code></td><tr><tr><td>vulnerabilities</td><td><img alt="critical: 0" src="https://img.shields.io/badge/critical-0-lightgrey"/> <img alt="high: 7" src="https://img.shields.io/badge/high-7-e25d68"/> <img alt="medium: 0" src="https://img.shields.io/badge/medium-0-lightgrey"/> <img alt="low: 0" src="https://img.shields.io/badge/low-0-lightgrey"/> <!-- unspecified: 0 --></td></tr>
<tr><td>platform</td><td>linux/amd64</td></tr>
<tr><td>size</td><td>60 MB</td></tr>
<tr><td>packages</td><td>4</td></tr>
</table>
</details></table>
</details>

<table>
<tr><td valign="top">
<details><summary><img alt="critical: 0" src="https://img.shields.io/badge/C-0-lightgrey"/> <img alt="high: 3" src="https://img.shields.io/badge/H-3-e25d68"/> <img alt="medium: 0" src="https://img.shields.io/badge/M-0-lightgrey"/> <img alt="low: 0" src="https://img.shields.io/badge/L-0-lightgrey"/> <!-- unspecified: 0 --><strong>msgpack</strong> <code>1.1.2</code> (pypi)</summary>

<small><code>pkg:pypi/msgpack@1.1.2</code></small><br/>
<a href="https://scout.docker.com/v/GHSA-6v7p-g79w-8964?s=github&n=msgpack&t=pypi&vr=%3C%3D1.2.0"><img alt="high 7.5: GHSA--6v7p--g79w--8964" src="https://img.shields.io/badge/GHSA--6v7p--g79w--8964-lightgrey?label=high%207.5&labelColor=e25d68"/></a> <i>Use After Free</i>

<table>
<tr><td>Affected range</td><td><code><=1.2.0</code></td></tr>
<tr><td>Fixed version</td><td><code>1.2.1</code></td></tr>
<tr><td>CVSS Score</td><td><code>7.5</code></td></tr>
<tr><td>CVSS Vector</td><td><code>CVSS:3.1/AV:N/AC:L/PR:N/UI:N/S:U/C:N/I:N/A:H</code></td></tr>
</table>

<details><summary>Description</summary>
<blockquote>

### Impact

If the Unpacker is used repeatedly after an error occurs, the process may crash with a SEGV.

If the Unpacker is used repeatedly to unpack untrusted input from external sources, it may be vulnerable to a DoS attack.

### Patches

v1.2.1

### Workarounds

Users should create a new Unpacker instead of reusing the same Unpacker after an error occurs.

Applying the above patch can prevent SEGV, but reusing the Streaming Unpacker after it has encountered an error will not yield correct data. If an error occurs during Streaming Unpacking, the Stream and Streaming Unpacker should be discarded.

Therefore, this is not just a workaround but the correct solution. The above patch only prevents crashes from incorrect usage.

</blockquote>
</details>

<a href="https://scout.docker.com/v/CVE-2026-57585?s=pypa&n=msgpack&t=pypi&vr=%3C1.2.1"><img alt="high 7.5: CVE--2026--57585" src="https://img.shields.io/badge/CVE--2026--57585-lightgrey?label=high%207.5&labelColor=e25d68"/></a> 

<table>
<tr><td>Affected range</td><td><code><1.2.1</code></td></tr>
<tr><td>Fixed version</td><td><code>1.2.1</code></td></tr>
<tr><td>CVSS Score</td><td><code>7.5</code></td></tr>
<tr><td>CVSS Vector</td><td><code>CVSS:3.1/AV:N/AC:L/PR:N/UI:N/S:U/C:N/I:N/A:H</code></td></tr>
<tr><td>EPSS Score</td><td><code>0.488%</code></td></tr>
<tr><td>EPSS Percentile</td><td><code>43rd percentile</code></td></tr>
</table>

<details><summary>Description</summary>
<blockquote>

MessagePack is the serializer implementation for Python msgpack.org. Prior to 1.2.1, there is an Out-of-bounds read/crash on Unpacker reuse after a caught error, potentially leading to a DoS attack.  If the Unpacker is used repeatedly after an error occurs, the process may crash with a SEGV. This issue has been fixed in version 1.2.1.

</blockquote>
</details>

<a href="https://scout.docker.com/v/CVE-2026-114613?s=github&n=msgpack&t=pypi&vr=%3C1.2.3"><img alt="high 7.5: CVE--2026--114613" src="https://img.shields.io/badge/CVE--2026--114613-lightgrey?label=high%207.5&labelColor=e25d68"/></a> <i>Missing Release of Memory after Effective Lifetime</i>

<table>
<tr><td>Affected range</td><td><code><1.2.3</code></td></tr>
<tr><td>Fixed version</td><td><code>1.2.3</code></td></tr>
<tr><td>CVSS Score</td><td><code>7.5</code></td></tr>
<tr><td>CVSS Vector</td><td><code>CVSS:3.1/AV:N/AC:L/PR:N/UI:N/S:U/C:N/I:N/A:H</code></td></tr>
<tr><td>EPSS Score</td><td><code>0.543%</code></td></tr>
<tr><td>EPSS Percentile</td><td><code>46th percentile</code></td></tr>
</table>

<details><summary>Description</summary>
<blockquote>

### Impact

The msgpack-python C extension (`msgpack._cmsgpack`) leaks a decoded map value when deserialization rejects a key with `strict_map_key=True` (the default). Repeated malformed inputs can cause unbounded process memory growth and denial of service in applications that deserialize attacker-controlled MessagePack data. Both `unpackb()` and the streaming `Unpacker` API are affected. The pure-Python fallback does not exhibit this leak in the reported tests.

The report measured approximately 4 MiB retained per failed parse and 100 MiB after 25 failed parses on Windows with Python 3.14 and msgpack 1.2.2. These are reporter-provided results.

### Additional impact: stale parser-stack references

The reference-ownership audit performed while fixing this leak found an
additional memory-safety issue in the streaming `Unpacker`.

After `unpack()` completed a nested container, an inactive parser-stack slot
could retain a non-owning pointer to the decoded object. A subsequent `skip()`
could reactivate that slot. If parsing then failed, context cleanup treated the
stale pointer as an owned reference and decremented it.

This corrupts the object's reference count and can result in a use-after-free
or double `Py_DECREF` when its actual owners later release it.

Although few users use this API, but those who do may experience crashes or unexpected errors due to a use-after-free.

### Details

In `msgpack/unpack.h`, `unpack_callback_map_item()` rejects keys that are neither `str` nor `bytes`. At this point the map value has already been constructed. The early error return does not release the value reference.

In `msgpack/unpack_template.h`, the value is held in the local `obj` in `unpack_execute()`. The `CT_MAP_VALUE` error path jumps to `_failed` without decrementing that reference. Cleanup of the parser stack does not recover the value because it is not stored in the stack. The fallback checks the key before decoding the value.

### Affected versions

The report reproduces the issue on **1.2.2** and reports it on development commit `475c1b7`. The affected-product field lists the reproduced release only; it is not a claim that earlier releases are unaffected.

The earliest affected release needs confirmation: the report's summary says 1.1.x through 1.2.2, while its root-cause analysis attributes introduction to commit `cd81370` (PR #673). Resolve this discrepancy before publishing a definitive affected-version range.

### Reproduction

Run in a disposable local process with the C extension installed:

```python
import msgpack

payload = msgpack.packb({42: b"A" * (4 * 1024 * 1024)}, use_bin_type=True)
msgpack.unpackb(payload)  # Raises ValueError; the report observes a 4 MiB leak.
```

Streaming API trigger:

```python
import msgpack

payload = msgpack.packb({42: b"A" * (4 * 1024 * 1024)}, use_bin_type=True)
u = msgpack.Unpacker()
u.feed(payload)
list(u)  # Same strict_map_key error path.
```

### Workarounds

The pure-Python fallback is reported not to leak on this path and may be used as a temporary workaround after application compatibility and performance checks. Request-size and rate limits may reduce the impact but do not eliminate cumulative leakage.

</blockquote>
</details>
</details></td></tr>

<tr><td valign="top">
<details><summary><img alt="critical: 0" src="https://img.shields.io/badge/C-0-lightgrey"/> <img alt="high: 2" src="https://img.shields.io/badge/H-2-e25d68"/> <img alt="medium: 0" src="https://img.shields.io/badge/M-0-lightgrey"/> <img alt="low: 0" src="https://img.shields.io/badge/L-0-lightgrey"/> <!-- unspecified: 0 --><strong>urllib3</strong> <code>2.7.0</code> (pypi)</summary>

<small><code>pkg:pypi/urllib3@2.7.0</code></small><br/>
<a href="https://scout.docker.com/v/CVE-2026-97689?s=github&n=urllib3&t=pypi&vr=%3E%3D1.10.3%2C%3C2.8.0"><img alt="high 8.9: CVE--2026--97689" src="https://img.shields.io/badge/CVE--2026--97689-lightgrey?label=high%208.9&labelColor=e25d68"/></a> <i>Allocation of Resources Without Limits or Throttling</i>

<table>
<tr><td>Affected range</td><td><code>>=1.10.3<br/><2.8.0</code></td></tr>
<tr><td>Fixed version</td><td><code>2.8.0</code></td></tr>
<tr><td>CVSS Score</td><td><code>8.9</code></td></tr>
<tr><td>CVSS Vector</td><td><code>CVSS:4.0/AV:N/AC:L/AT:P/PR:N/UI:N/VC:N/VI:N/VA:H/SC:N/SI:N/SA:H</code></td></tr>
<tr><td>EPSS Score</td><td><code>0.335%</code></td></tr>
<tr><td>EPSS Percentile</td><td><code>27th percentile</code></td></tr>
</table>

<details><summary>Description</summary>
<blockquote>

## Impact

urllib3's [streaming API](https://urllib3.readthedocs.io/en/2.7.0/advanced-usage.html#streaming-and-i-o) is designed for efficiently handling large HTTP responses by reading the content in chunks, rather than loading the entire response body into memory at once. When decoding a [chunked-transfer-encoded response](https://httpwg.org/specs/rfc9112.html#chunked.encoding), this API reads each chunk's size field by buffering until it sees `\n` or EOF.

A malicious HTTP server can return `Transfer-Encoding: chunked` and then send a very long run of bytes without any newline, causing the streaming client to buffer that entire run before urllib3 can reject the chunk size as invalid and allocate more memory than intended.

To fix the issue, we'll reject chunk-size fields larger than 65536 bytes, as already done in the non-streaming case, which is currently handled by the Python standard library. Note that this only applies to reading the chunk-size field, not the chunk data, which is already handled correctly. Thus, there shouldn't be any impact for non-malicious servers.

## Affected usages

Applications and libraries using urllib3 versions earlier than 2.8.0 may be affected when streaming a chunked response from untrusted sources. Specifically, this affects the [read_chunked()](https://urllib3.readthedocs.io/en/stable/reference/urllib3.response.html#urllib3.response.BaseHTTPResponse.read_chunked) and [stream()](https://urllib3.readthedocs.io/en/stable/reference/urllib3.response.html#urllib3.response.BaseHTTPResponse.stream) methods of the HTTPResponse object.

This also affects requests streaming API, which uses urllib3 under the hood.

## Remediation

Upgrade to urllib3 version 2.8.0 or later, where chunk-size fields larger than 65536 will be rejected. If upgrading is not immediately possible, consider reading the response at once using the [read()](https://urllib3.readthedocs.io/en/stable/reference/urllib3.response.html#urllib3.response.BaseHTTPResponse.read) method.

</blockquote>
</details>

<a href="https://scout.docker.com/v/CVE-2026-97687?s=github&n=urllib3&t=pypi&vr=%3E%3D1.26.0%2C%3C2.8.0"><img alt="high 7.6: CVE--2026--97687" src="https://img.shields.io/badge/CVE--2026--97687-lightgrey?label=high%207.6&labelColor=e25d68"/></a> <i>Improper Certificate Validation</i>

<table>
<tr><td>Affected range</td><td><code>>=1.26.0<br/><2.8.0</code></td></tr>
<tr><td>Fixed version</td><td><code>2.8.0</code></td></tr>
<tr><td>CVSS Score</td><td><code>7.6</code></td></tr>
<tr><td>CVSS Vector</td><td><code>CVSS:4.0/AV:N/AC:L/AT:P/PR:N/UI:P/VC:H/VI:H/VA:N/SC:N/SI:N/SA:N</code></td></tr>
<tr><td>EPSS Score</td><td><code>0.206%</code></td></tr>
<tr><td>EPSS Percentile</td><td><code>11th percentile</code></td></tr>
</table>

<details><summary>Description</summary>
<blockquote>

## Impact

urllib3 supports configuring TLS independently for an HTTPS proxy and the target server.

`proxy_ssl_context`, `proxy_assert_hostname`, and `proxy_assert_fingerprint` configure the TLS connection to the proxy. `ssl_context` and the other target-specific TLS parameters configure the connection to the target server.

In urllib3 versions 1.26.0 through 2.7.0, these configurations were not consistently separated. Depending on the proxy mode, urllib3 could:

1. Ignore `proxy_ssl_context` and use the target server's SSL context for the TLS connection to an HTTPS forwarding proxy.
2. Override the HTTPS proxy's certificate-verification policy with the target server's certificate-verification policy.
3. Apply target-specific SNI, hostname assertions, certificate fingerprint assertions, or TLS client credentials to the TLS connection to an HTTPS forwarding proxy.

In particular, configuring `cert_reqs="CERT_NONE"` for a target server could overwrite the `verify_mode` of the SSL context configured for the HTTPS proxy. This modification occurred in place and persisted on the context object, potentially disabling proxy certificate verification for later connections that reused the same context.

An attacker able to intercept the connection to an HTTPS proxy may be able to impersonate the proxy when the effective proxy TLS configuration disables certificate verification or otherwise accepts the attacker's certificate. This may occur, for example, when the target server's trust or identity policy is incorrectly applied to the proxy connection.

When HTTPS forwarding is enabled, an impersonated proxy can observe or modify forwarded requests and responses, potentially exposing credentials, authentication tokens, request bodies, response data, and other sensitive information.

A TLS client certificate intended for the target server may also be presented to the proxy or to an attacker impersonating it. This can disclose the client's identity and provide proof of possession of the corresponding private key. The private key itself is not transmitted during the TLS handshake.

In CONNECT tunneling mode, impersonating the HTTPS proxy does not by itself defeat the separate end-to-end TLS connection between the client and the target server.

## Affected Usages

Code using urllib3 versions 1.26.0 through 2.7.0 may be affected in any of the following cases.

### 1. The target SSL context is used for an HTTPS forwarding proxy

HTTPS requests are forwarded through an HTTPS proxy with `use_forwarding_for_https=True`, and `proxy_ssl_context` is configured for the proxy.

urllib3 may ignore `proxy_ssl_context` and use the target server's `ssl_context` for the proxy TLS handshake. The proxy may therefore be verified using the target server's trust and certificate policy instead of the policy explicitly configured for the proxy.

### 2. The target verification policy overrides the proxy policy

An HTTPS proxy is configured with `proxy_ssl_context`, while the target server uses a different certificate-verification policy.

urllib3 may apply the target server's `cert_reqs` value to the proxy SSL context. For example, setting `cert_reqs="CERT_NONE"` for the target server may also disable certificate verification for the HTTPS proxy, even when `proxy_ssl_context` was configured to require verification.

This issue can affect the TLS connection to an HTTPS proxy in both forwarding and CONNECT tunneling configurations.

### 3. A mutated proxy SSL context is reused

The same SSL context is reused as `proxy_ssl_context` across multiple connections, and certificate verification is disabled for one target server.

urllib3 may modify the proxy SSL context's `verify_mode` in place. Later connections that reuse the same context may therefore connect to the HTTPS proxy without certificate verification.

### 4. Target-specific TLS identity or credentials are applied to the proxy

HTTPS requests are forwarded through an HTTPS proxy with `use_forwarding_for_https=True`, and target-specific SNI, hostname assertions, certificate fingerprint assertions, or TLS client credentials are configured.

urllib3 may apply these target-specific settings to the proxy TLS handshake. This may cause urllib3 to:

- send SNI intended for the target server to the proxy;
- verify the proxy using a hostname or certificate fingerprint intended for the target server; or
- present a TLS client certificate intended for the target server to the proxy.

Code connecting through a plain HTTP proxy does not establish a TLS connection to the proxy and is not affected by this issue.

## Remediation

Upgrade to urllib3 2.8.0 or later.

urllib3 2.8.0 independently applies the explicitly configured `proxy_ssl_context` and proxy-specific certificate assertions to the HTTPS proxy connection. Target-specific SNI, certificate assertions, and TLS client certificate parameters are no longer applied to the HTTPS proxy handshake.

For backward compatibility, when an HTTPS proxy is used with `use_forwarding_for_https=True` and `proxy_ssl_context` is not provided, urllib3 2.8.0 continues to use `ssl_context` for the TLS connection to the proxy. This configuration emits a `FutureWarning`. In urllib3 3.0, passing `ssl_context` with `use_forwarding_for_https=True` for an HTTPS proxy will raise an error. Applications should use `proxy_ssl_context` to configure TLS for an HTTPS forwarding proxy.

The fixes were implemented in commits b6447295fff7b38fdffc67e0df9712d60cef3cc3 and 07408cec79d1856d81bb42c74a904a24fdb9e465.

</blockquote>
</details>
</details></td></tr>

<tr><td valign="top">
<details><summary><img alt="critical: 0" src="https://img.shields.io/badge/C-0-lightgrey"/> <img alt="high: 1" src="https://img.shields.io/badge/H-1-e25d68"/> <img alt="medium: 0" src="https://img.shields.io/badge/M-0-lightgrey"/> <img alt="low: 0" src="https://img.shields.io/badge/L-0-lightgrey"/> <!-- unspecified: 0 --><strong>setuptools</strong> <code>70.3.0</code> (pypi)</summary>

<small><code>pkg:pypi/setuptools@70.3.0</code></small><br/>
<a href="https://scout.docker.com/v/CVE-2025-47273?s=github&n=setuptools&t=pypi&vr=%3C78.1.1"><img alt="high 7.7: CVE--2025--47273" src="https://img.shields.io/badge/CVE--2025--47273-lightgrey?label=high%207.7&labelColor=e25d68"/></a> <i>Improper Limitation of a Pathname to a Restricted Directory ('Path Traversal')</i>

<table>
<tr><td>Affected range</td><td><code><78.1.1</code></td></tr>
<tr><td>Fixed version</td><td><code>78.1.1</code></td></tr>
<tr><td>CVSS Score</td><td><code>7.7</code></td></tr>
<tr><td>CVSS Vector</td><td><code>CVSS:4.0/AV:N/AC:L/AT:N/PR:N/UI:N/VC:N/VI:H/VA:N/SC:N/SI:N/SA:N/E:P</code></td></tr>
<tr><td>EPSS Score</td><td><code>1.620%</code></td></tr>
<tr><td>EPSS Percentile</td><td><code>77th percentile</code></td></tr>
</table>

<details><summary>Description</summary>
<blockquote>

### Summary 
A path traversal vulnerability in `PackageIndex` was fixed in setuptools version 78.1.1

### Details
```
    def _download_url(self, url, tmpdir):
        # Determine download filename
        #
        name, _fragment = egg_info_for_url(url)
        if name:
            while '..' in name:
                name = name.replace('..', '.').replace('\\', '_')
        else:
            name = "__downloaded__"  # default if URL has no path contents

        if name.endswith('.[egg.zip](http://egg.zip/)'):
            name = name[:-4]  # strip the extra .zip before download

 -->       filename = os.path.join(tmpdir, name)
```

Here: https://github.com/pypa/setuptools/blob/6ead555c5fb29bc57fe6105b1bffc163f56fd558/setuptools/package_index.py#L810C1-L825C88

`os.path.join()` discards the first argument `tmpdir` if the second begins with a slash or drive letter.
`name` is derived from a URL without sufficient sanitization. While there is some attempt to sanitize by replacing instances of '..' with '.', it is insufficient.

### Risk Assessment
As easy_install and package_index are deprecated, the exploitation surface is reduced.
However, it seems this could be exploited in a similar fashion like https://github.com/advisories/GHSA-r9hx-vwmv-q579, and as described by POC 4 in https://github.com/advisories/GHSA-cx63-2mw6-8hw5 report: via malicious URLs present on the pages of a package index.

### Impact
An attacker would be allowed to write files to arbitrary locations on the filesystem with the permissions of the process running the Python code, which could escalate to RCE depending on the context.

### References
https://huntr.com/bounties/d6362117-ad57-4e83-951f-b8141c6e7ca5
https://github.com/pypa/setuptools/issues/4946

</blockquote>
</details>
</details></td></tr>

<tr><td valign="top">
<details><summary><img alt="critical: 0" src="https://img.shields.io/badge/C-0-lightgrey"/> <img alt="high: 1" src="https://img.shields.io/badge/H-1-e25d68"/> <img alt="medium: 0" src="https://img.shields.io/badge/M-0-lightgrey"/> <img alt="low: 0" src="https://img.shields.io/badge/L-0-lightgrey"/> <!-- unspecified: 0 --><strong>django</strong> <code>5.2.13</code> (pypi)</summary>

<small><code>pkg:pypi/django@5.2.13</code></small><br/>
<a href="https://scout.docker.com/v/CVE-2026-15307?s=github&n=django&t=pypi&vr=%3C5.2.17"><img alt="high 8.7: CVE--2026--15307" src="https://img.shields.io/badge/CVE--2026--15307-lightgrey?label=high%208.7&labelColor=e25d68"/></a> <i>External Control of File Name or Path</i>

<table>
<tr><td>Affected range</td><td><code><5.2.17</code></td></tr>
<tr><td>Fixed version</td><td><code>5.2.17</code></td></tr>
<tr><td>CVSS Score</td><td><code>8.7</code></td></tr>
<tr><td>CVSS Vector</td><td><code>CVSS:4.0/AV:N/AC:L/AT:N/PR:L/UI:N/VC:H/VI:H/VA:H/SC:N/SI:N/SA:N</code></td></tr>
<tr><td>EPSS Score</td><td><code>1.134%</code></td></tr>
<tr><td>EPSS Percentile</td><td><code>67th percentile</code></td></tr>
</table>

<details><summary>Description</summary>
<blockquote>

An issue was discovered in Django 5.2 before 5.2.17 and 6.0 before 6.0.8.
GeoDjango spatial lookups optimistically parse the right-hand-side value as a raster by passing it to the `django.contrib.gis.gdal.GDALRaster` constructor. Any value used in a spatial lookup against a `GeometryField` or `RasterField` reaches this constructor, including untrusted input, for example a spatial-field filter submitted through the Django admin changelist query string by a staff user with view permission. A `dict`, or a `str` holding its JSON representation, is opened in write mode regardless of the constructor's `write=False` default, allowing a file with an attacker-chosen name and contents to be written through a file-backed GDAL driver. Any other `str` is treated as a datasource, allowing an outbound network request through a GDAL virtual filesystem handler. Writing a file to a location later imported by the application can result in remote code execution.
Earlier, unsupported Django series (such as 5.1.x, 5.0.x, and 4.2.x) were not evaluated and may also be affected.
Django would like to thank Bence Nagy, localhost-detect, and kimchunbok_ for reporting this issue.

</blockquote>
</details>
</details></td></tr>
</table>

