<div align="center">

# 🏔️ TryHackMe — Valley

**"Can you find your way into the Valley?"**

![Platform](https://img.shields.io/badge/Platform-TryHackMe-red?style=flat-square)
![Difficulty](https://img.shields.io/badge/Difficulty-Medium-orange?style=flat-square)
![Category](https://img.shields.io/badge/Category-Web%20Exploitation%20%2B%20Priv%20Esc-blue?style=flat-square)
![Status](https://img.shields.io/badge/Status-User%20Flag%20Obtained-success?style=flat-square)

</div>

---

## 📋 Room Info

| Field | Value |
|---|---|
| **Platform** | TryHackMe |
| **Room** | [Valley](https://tryhackme.com/room/valley) |
| **Category** | Web Exploitation, OSINT-in-source, Credential Hunting, Network Forensics, Privilege Escalation |
| **Difficulty** | Medium |
| **Date Solved** | August 2026 |
| **Tools Used** | `nmap`, `gobuster`, Firefox DevTools (view-source), `ftp`, `wireshark`, `ssh`, CrackStation |

---

## 🎯 Objective

Standard boot2root flow: get a foothold on the box, find `user.txt`, escalate privileges. What made Valley interesting wasn't brute-forcing anything — it was **following a trail of breadcrumbs**: a dev's sloppy notes led to hardcoded JS credentials, which led to an FTP server, which led to packet captures, which led to real SSH credentials. Every step fed the next.

---

## 1️⃣ Reconnaissance

Started with a full port sweep to make sure nothing was hiding on a non-standard port, then a targeted service/version scan on what came back.

```bash
nmap -sV -T4 -Pn 10.128.176.159
```

**Result:**
```
PORT   STATE SERVICE VERSION
22/tcp open  ssh     OpenSSH 8.2p1 Ubuntu 4ubuntu0.5 (Ubuntu Linux; protocol 2.0)
80/tcp open  http    Apache httpd 2.4.41 ((Ubuntu))
```

**Reasoning:** Only two services, both common and patched versions. Neither OpenSSH 8.2p1 nor Apache 2.4.41 has a known unauthenticated RCE — a quick `searchsploit` check on both confirmed nothing usable. This told me immediately: **the vulnerability lives in the web application itself, not the underlying services.** Attack surface = port 80.

---

## 2️⃣ Initial Web Recon

Visited `http://10.128.176.159` directly — a static "Valley Photo Co." site, photography-business themed, with links for a gallery and pricing. Nothing obviously exploitable on the surface (no visible login form, no upload feature).

Rather than blindly fuzzing right away, I checked the page source and `robots.txt` first — standard practice before burning wordlist time. Nothing useful there, so I moved to directory enumeration.

---

## 3️⃣ Directory Enumeration — Round 1

```bash
gobuster dir -u http://10.128.176.159 -w /usr/share/wordlists/dirb/common.txt -x php,html,txt,bak
```

**Result:**
```
gallery      (Status: 301) → /gallery/
index.html   (Status: 200)
pricing      (Status: 301) → /pricing/
static       (Status: 301) → /static/
```

(`.htaccess` / `.htpasswd` variants all returned expected `403` — Apache's default protection, not useful here.)

`gallery` and `pricing` matched the site's own navigation — expected, low priority. **`static/` stood out** — generic name, worth digging into since static asset directories often get overlooked by whoever configured directory listing permissions.

---

## 4️⃣ Directory Enumeration — Round 2 (the actual lead)

```bash
gobuster dir -u http://10.128.176.159/static/ -w /usr/share/wordlists/dirb/common.txt
```

**Result (partial):**
```
00   (Status: 200) [Size: 127]
11   (Status: 200) [Size: 627909]
3    (Status: 200) [Size: 421858]
```

**Reasoning:** These aren't real English wordlist matches — they're numeric names, meaning they were only found because `common.txt` happens to include short numeric strings. The **tiny file size on `00` (127 bytes)** compared to the others (600KB+, clearly images) immediately flagged it as text content worth reading directly rather than a photo.

---

## 5️⃣ The Dev Notes Leak

Visiting `http://10.128.176.159/static/00` directly revealed a plaintext note, clearly left behind by a developer and never cleaned up:

```
dev notes from valleyDev:
-add wedding photo examples
-redo the editing on #4
-remove /dev1243224123123
-check for SIEM alerts
```

**This is the single most important find in the whole box.** A throwaway internal note directly disclosed a hidden path (`/dev1243224123123`) that was never linked anywhere on the site and would never have shown up in a generic wordlist scan. This is a textbook example of **information disclosure through developer carelessness** — exactly the kind of finding I'd flag in a real engagement report.

---

## 6️⃣ Following the Leak → Dev Login Panel

Navigating to `http://10.128.176.159/dev1243224123123/` revealed a **"Valley Photo Co. Dev Login"** panel — username/password form, clearly not meant for public users.

Rather than guess credentials or brute-force it, I went straight to `view-source:` on the page. Two scripts were loaded: `dev.js` and `button.js`.

---

## 7️⃣ Client-Side Logic Flaw — Hardcoded Credentials

Reading `dev.js` in the browser's source view exposed the entire authentication logic running **client-side**, including this:

```javascript
loginButton.addEventListener("click", (e) => {
    e.preventDefault();
    const username = loginForm.username.value;
    const password = loginForm.password.value;

    if (username === "siemDev" && password === "california") {
        window.location.href = "/dev1243224123123/devNotes37370.txt";
    } else {
        loginErrorMsg.style.opacity = 1;
    }
});
```

**This is a critical, classic vulnerability:** authentication logic that should live server-side was implemented entirely in client-side JavaScript, with the credentials hardcoded in plaintext. Anyone who reads the page source gets the login instantly — no exploitation skill required beyond knowing to check `view-source:`.

Using `siemDev` / `california` in the login form redirected to `devNotes37370.txt`, which disclosed the credentials and port for an FTP service running elsewhere on the box (non-standard port `37370`).

---

## 8️⃣ FTP — Picking Up the Trail

```bash
ftp 10.128.176.159 37370
Name: siemDev
Password: ********
230 Login successful.
```

Once inside, listing the directory revealed three packet capture files:

```
-rw-rw-r--   1 1000  1000     7272 Mar 06 2023 siemFTP.pcapng
-rw-rw-r--   1 1000  1000  1978716 Mar 06 2023 siemHTTP1.pcapng
-rw-rw-r--   1 1000  1000  1972448 Mar 06 2023 siemHTTP2.pcapng
```

**Reasoning:** The dev note earlier said *"check for SIEM alerts"* — these filenames (`siemFTP`, `siemHTTP1/2`) directly matched that hint. Pulled all three down locally with `mget` for offline analysis.

---

## 9️⃣ Network Forensics — Wireshark

Opened each capture in Wireshark, filtered on `http` to skip irrelevant background noise (OCSP cert-check traffic, etc.) and focus on actual application traffic.

Inside `siemHTTP2.pcapng`, one packet stood out: a `POST /index.html` request with form-encoded data. Wireshark's protocol dissector broke it down cleanly:

```
Form item: "uname" = "valleyDev"
Form item: "psw"   = "ph0t0s1234"
Form item: "remember" = "on"
```

**This is exactly why the pcap files existed** — someone had logged into the site at some point while the traffic was being captured (deliberately, for "SIEM monitoring"), and the login was sent over plaintext HTTP with no TLS. Classic **cleartext credential transmission** — a login captured on the wire is a login handed to anyone with visibility on that traffic.

---

## 🔟 Foothold — SSH as valleyDev

```bash
ssh valleyDev@10.128.176.159
Password: ph0t0s1234
```

Logged in successfully. Confirmed access with `ls -la`:

```
-rw-rw-rw-  1 root  root  24 Mar 13 2023 user.txt
```

```
cat user.txt
```

✅ **User flag obtained.**

---

## 1️⃣1️⃣ Privilege Escalation — Hash Discovery

While enumerating further on the box, came across garbled/binary-adjacent output containing a login banner fragment (*"Welcome to Valley Inc. Authentica[tion]..."*) alongside an isolated **MD5 hash**:

```
e6722920bab2326f8217e4
```

Rather than trying to crack this locally with a limited wordlist (time-consuming and not guaranteed), used **CrackStation** — a free rainbow-table-backed hash lookup covering MD5/NTLM/SHA family hashes — since MD5 with no visible salt is exactly the profile it's built for.

**Result:**
```
Hash: e6722920bab2326f8217e4
Type: MD5
Result: liberty123
```

---

## 1️⃣2️⃣ Lateral Movement — SSH as valley

```bash
ssh valley@10.128.176.159
Password: liberty123
```

✅ **Second foothold confirmed** — moved from `valleyDev` to the `valley` user using the cracked credential.

> 📌 *Placeholder — root escalation path and final `root.txt` flag to be added here once documented (pending the last two screenshots).*

---

## 🧠 Lessons Learned

- **Always check `view-source:` before brute-forcing a login form.** Client-side auth logic is a real vulnerability class, not just a CTF trope — I've seen sloppier versions of this in actual web pentests.
- **Leftover dev notes and comments are free reconnaissance.** The `/static/00` file alone unlocked half the box. In a real engagement, this is exactly the kind of finding that goes straight into a findings register.
- **Packet captures are a legitimate credential-hunting target**, not just a "Wireshark 101" exercise — cleartext HTTP logins caught on the wire are a direct path to compromise.
- **MD5 hashes without a salt are effectively already broken** — don't waste time brute-forcing locally when a service like CrackStation exists for common/weak passwords.
- **Chain every finding.** Nothing here was a single silver-bullet exploit — it was five small, individually "minor" findings chained together into full compromise. This mirrors real-world engagements more than a single flashy CVE would.

---

## 🛠️ Skills Demonstrated

`Web Enumeration` · `Information Disclosure Analysis` · `Client-Side Code Review` · `FTP Exploitation` · `Network Traffic Analysis (Wireshark)` · `Credential Hunting` · `Hash Cracking` · `Linux Privilege Escalation` · `Chained Exploitation Methodology`

---

## 📚 References

- [OWASP — Client-Side Enforcement of Server-Side Security](https://owasp.org/www-community/attacks/Client-side_enforcement_of_server-side_security)
- [Wireshark HTTP Filter Reference](https://www.wireshark.org/docs/dfref/h/http.html)
- [CrackStation](https://crackstation.net)
