<h2>:mag: Vulnerabilities of <code>satell-rag-api:phase6-candidate</code></h2>

<details open="true"><summary>:package: Image Reference</strong> <code>satell-rag-api:phase6-candidate</code></summary>
<table>
<tr><td>digest</td><td><code>sha256:0ab84e45ec8fd0f85a371d62d6d0c0bde01ce0b9f1dbb72fdc869d946c2f8c78</code></td><tr><tr><td>vulnerabilities</td><td><img alt="critical: 0" src="https://img.shields.io/badge/critical-0-lightgrey"/> <img alt="high: 3" src="https://img.shields.io/badge/high-3-e25d68"/> <img alt="medium: 0" src="https://img.shields.io/badge/medium-0-lightgrey"/> <img alt="low: 0" src="https://img.shields.io/badge/low-0-lightgrey"/> <!-- unspecified: 0 --></td></tr>
<tr><td>platform</td><td>linux/amd64</td></tr>
<tr><td>size</td><td>152 MB</td></tr>
<tr><td>packages</td><td>3</td></tr>
</table>
</details></table>
</details>

<table>
<tr><td valign="top">
<details><summary><img alt="critical: 0" src="https://img.shields.io/badge/C-0-lightgrey"/> <img alt="high: 3" src="https://img.shields.io/badge/H-3-e25d68"/> <img alt="medium: 0" src="https://img.shields.io/badge/M-0-lightgrey"/> <img alt="low: 0" src="https://img.shields.io/badge/L-0-lightgrey"/> <!-- unspecified: 0 --><strong>openssl</strong> <code>3.5.7-1~deb13u3</code> (deb)</summary>

<small><code>pkg:deb/debian/openssl@3.5.7-1~deb13u3?os_distro=trixie&os_name=debian&os_version=13</code></small><br/>
<a href="https://scout.docker.com/v/CVE-2026-107493?s=debian&n=openssl&ns=debian&t=deb&osn=debian&osv=13&vr=%3E0"><img alt="high : CVE--2026--107493" src="https://img.shields.io/badge/CVE--2026--107493-lightgrey?label=high%20&labelColor=e25d68"/></a> 

<table>
<tr><td>Affected range</td><td><code>>0</code></td></tr>
<tr><td>Fixed version</td><td><strong>Not Fixed</strong></td></tr>
<tr><td>EPSS Score</td><td><code>0.143%</code></td></tr>
<tr><td>EPSS Percentile</td><td><code>4th percentile</code></td></tr>
</table>

<details><summary>Description</summary>
<blockquote>

Issue summary: When an application passes a stack to PEM_X509_INFO_read_bio_ex() to add entries to, and reading fails, OpenSSL frees every entry in the stack, both the old ones and any new ones, but leaves them in the stack.  Impact summary: An application that passes an existing stack to PEM_X509_INFO_read_bio_ex() and keeps using it after a failed read may use memory that was already freed. This can cause a crash or, in principle, memory corruption. Malformed PEM data can make the read fail, but only applications that pass an existing stack are affected, and OpenSSL itself does not do this.  CWE: CWE-416: Use After Free  Description: PEM_X509_INFO_read_bio_ex() reads certificates, CRLs and private keys from PEM data and adds them to a stack of X509_INFO structures. If the application passes a stack that is not NULL, the function adds the new entries to it and must leave the entries that are already there unchanged.  If reading fails, the function frees every entry in the stack. This includes the entries that were there before the call, and the entries added by the call. It does not remove these entries from the stack, so the stack keeps pointers to freed memory. The failure can happen at any point, even before any entry was added. A PEM item with invalid content is enough.  This also happens if the stack was empty: entries added before the failure are freed but stay in the stack.  An application that then reads or frees the stack will use memory that was already freed. This can crash the application or, in principle, corrupt memory.  Only applications that pass a stack that is not NULL are affected. OpenSSL itself never does this. Its own callers, including the code that TLS uses to load CA certificates, always pass NULL. When the stack is NULL, the function frees only the entries that it created itself, which is safe. We expect that very few applications pass an existing stack. An attacker can make the read fail with malformed PEM data, but cannot make an application pass an existing stack.  The same problem affects PEM_X509_INFO_read_bio(), PEM_X509_INFO_read() and PEM_X509_INFO_read_ex(), which use the same code. OpenSSL 1.1.1 and 1.0.2 have only the first two of these functions.  FIPS impact: no The affected code is outside the FIPS module boundary.

---
- openssl <unfixed>
https://openssl-library.org/news/secadv/20261117.txt

</blockquote>
</details>

<a href="https://scout.docker.com/v/CVE-2026-84786?s=debian&n=openssl&ns=debian&t=deb&osn=debian&osv=13&vr=%3E0"><img alt="high : CVE--2026--84786" src="https://img.shields.io/badge/CVE--2026--84786-lightgrey?label=high%20&labelColor=e25d68"/></a> 

<table>
<tr><td>Affected range</td><td><code>>0</code></td></tr>
<tr><td>Fixed version</td><td><strong>Not Fixed</strong></td></tr>
<tr><td>EPSS Score</td><td><code>0.093%</code></td></tr>
<tr><td>EPSS Percentile</td><td><code>1st percentile</code></td></tr>
</table>

<details><summary>Description</summary>
<blockquote>

A DANE-enabled TLS client may crash by dereferencing a NULL pointer when processing an unusual combination of certificate and TLSA records.

---
- openssl <unfixed>
https://github.com/openssl/openssl/pull/33634

</blockquote>
</details>

<a href="https://scout.docker.com/v/CVE-2026-107496?s=debian&n=openssl&ns=debian&t=deb&osn=debian&osv=13&vr=%3E0"><img alt="high : CVE--2026--107496" src="https://img.shields.io/badge/CVE--2026--107496-lightgrey?label=high%20&labelColor=e25d68"/></a> 

<table>
<tr><td>Affected range</td><td><code>>0</code></td></tr>
<tr><td>Fixed version</td><td><strong>Not Fixed</strong></td></tr>
<tr><td>EPSS Score</td><td><code>0.336%</code></td></tr>
<tr><td>EPSS Percentile</td><td><code>28th percentile</code></td></tr>
</table>

<details><summary>Description</summary>
<blockquote>

Issue summary: Encrypting a CMS message to an EC certificate whose group order is 1 may cause CMS_encrypt() or CMS_encrypt_ex() to loop indefinitely.  Impact summary: An attacker able to supply the recipient certificate to an application performing CMS encryption can cause that application to loop indefinitely, consuming CPU and resulting in Denial of Service.  CWE: CWE-835: Loop with Unreachable Exit Condition ('Infinite Loop')  Description: CMS_encrypt() and CMS_encrypt_ex() encrypt a message to one or more recipient certificates and, for an EC recipient, generate an ephemeral key in the recipient's group. If the certificate declares a group order of 1, random scalar generation can only produce zero. The key generation routine then retries without limit while waiting for a nonzero private scalar, so the call never returns.  The OpenSSL TLS and QUIC implementations do not use this path. An application is exposed only if it calls CMS_encrypt() or CMS_encrypt_ex() with a recipient certificate whose EC parameters are attacker-controlled. Certificates with normal EC group orders do not trigger the loop.  OpenSSL 4.0 and later reject unknown explicit EC groups in default builds. These versions are affected only when configured with the enable-ec_explicit_curves option.  The result is a hang that consumes a CPU core until the process is interrupted, a Denial of Service. The severity is Low because the attacker must supply the recipient certificate and the application must choose to encrypt to it; ordinary CMS encryption to trusted recipients is unaffected.  The fix makes EC key generation fail when the group has no valid nonzero private scalar, instead of retrying indefinitely.  FIPS impact: no The FIPS modules in 4.1, 4.0, 3.5 and 3.0 are not affected. The FIPS provider does not support arbitrary explicit EC domain parameters, so an order-1 group is rejected during key import before the vulnerable key generation path is reached.

---
- openssl <unfixed>
https://openssl-library.org/news/secadv/20261110.txt

</blockquote>
</details>
</details></td></tr>
</table>

