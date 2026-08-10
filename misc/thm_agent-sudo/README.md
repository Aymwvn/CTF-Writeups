<div align="center">

# 👽 TryHackMe — Agent Sudo

**"You found a secret server located under the deep sea. Your task is to hack inside the server and reveal the truth."**

![Platform](https://img.shields.io/badge/Platform-TryHackMe-red?style=flat-square)
![Difficulty](https://img.shields.io/badge/Difficulty-Medium-orange?style=flat-square)
![Category](https://img.shields.io/badge/Category-Enumeration%20%2B%20Steganography%20%2B%20PrivEsc-blue?style=flat-square)
![Status](https://img.shields.io/badge/Status-Rooted-success?style=flat-square)

</div>

![Room banner](./screenshots/00_room_banner.png)

---

## 📋 Room Info

| Field | Value |
|---|---|
| **Platform** | TryHackMe |
| **Room** | Agent Sudo |
| **Tools Used** | `nmap`, `curl`, `hydra`, `ftp`, `binwalk`, `7z`, `zip2john` + `john`, `steghide`, Google reverse image search, CyberChef, `ssh`, `sudo` |
| **Date Completed** | August 2026 |

> 🎯 This is a full multi-stage box, structured exactly around the room's 5 official tasks. Every answer below is marked **Confirmed** (I have a screenshot proving it) or **Not captured** (I know the concept but didn't screenshot that exact step) — being honest about gaps makes this reference more useful than pretending every box was checked.

---

## 🔍 Task 2 — Enumeration

### Finding the hidden page via a User-Agent trick

Standard recon would normally start with `nmap` to find open ports (21/FTP, 22/SSH, 80/HTTP is the typical spread for a box like this). Visiting the web service directly with `curl` revealed something unusual:

```bash
curl -A "R" -L 10.129.135.206
```

![curl with custom User-Agent revealing hidden announcement](./screenshots/01_curl_useragent_secret_page.png)

**What's happening here:** the `-A "R"` flag sets the **User-Agent header** — normally this just identifies what browser/tool is making the request (Chrome, Firefox, curl, etc.), but this server is checking it for something else entirely. The response is a custom HTML page addressed to "agents," explicitly instructing: *"Use your own codename as user-agent to access the site."* This is **not a real security control** in any technical sense — User-Agent headers are trivially spoofable by anyone — but it's the room's way of gating a hidden page behind a piece of trivia only someone who'd already found a clue (a codename) would know to try.

### 📝 Task 2 — Questions & Answers

| Question | Answer |
|---|---|
| How many open ports? | *Not captured — didn't screenshot the nmap scan, but the service spread (FTP, SSH, HTTP) implies 3* |
| How do you redirect yourself to a secret page? | **Confirmed** — by setting a custom `User-Agent` HTTP header (via `curl -A`) to match a known agent codename |
| What is the agent name? | **Confirmed** — the announcement page is signed **"Agent R"** |

---

## 🔓 Task 3 — Hash Cracking and Brute-Force

### Step 1 — Brute-forcing the FTP login with Hydra

```bash
hydra -l chris -P /usr/share/wordlists/rockyou.txt 10.129.135.206 ftp
```

![Hydra cracking the FTP password](./screenshots/02_hydra_ftp_bruteforce.png)

**Why Hydra here and not John:** Hydra is built for **online, live-service brute-forcing** (FTP, SSH, HTTP login forms, etc.) — it actually connects and tries each credential pair against the running service in real time. John the Ripper, by contrast, cracks **offline hashes** you already have in hand. Since we only had a username (`chris`) and needed to test live logins against a running FTP server, Hydra is the right tool for the job.

**Result:** `login: chris   password: crystal`

### Step 2 — Logging into FTP and grabbing the files

```bash
ftp ftp://chris:crystal@10.129.135.206
ftp> ls -la
ftp> mget *
```

![FTP login and downloading all files](./screenshots/03_ftp_login_download_files.png)

Three files pulled down: `To_agentJ.txt`, `cute-alien.jpg`, `cutie.png`.

### Step 3 — Finding a hidden archive inside an image with `binwalk`

```bash
binwalk cutie.png
```

![binwalk revealing an embedded ZIP inside the PNG](./screenshots/04_binwalk_hidden_zip.png)

**What `binwalk` does:** it scans a file for the **signature bytes of other embedded file types** — since file formats have recognizable "magic bytes" at fixed offsets, `binwalk` can spot a ZIP archive's signature sitting *inside* what looks like an ordinary PNG. This is a classic steganography/file-smuggling technique: a PNG viewer only reads until it's satisfied it has a valid image, completely ignoring extra bytes appended after the actual image data ends.

Result: an encrypted ZIP archive (`To_agentR.txt` inside it) was hiding inside `cutie.png`.

```bash
binwalk -e cutie.png
cd _cutie.png.extracted
ls
```

![Extracted folder contents](./screenshots/05_extracted_folder_contents.png)

`8702.zip` — the embedded archive, successfully carved out.

### Step 4 — Cracking the ZIP password

```bash
zip2john 8702.zip > zip.hash
john zip.hash
```

![zip2john + John cracking the ZIP password](./screenshots/06_zip2john_crack_alien.png)

**Cracked:** `alien` — fitting, given the "cute-alien" and UFO theming of the whole room.

```bash
7z e 8702.zip
# Enter password: alien
```

![7z extracting with the cracked password](./screenshots/07_7z_extract_password.png)

### Step 5 — Steganography on the second image

The other downloaded file, `cute-alien.jpg`, turned out to hide data using **steghide** (a different steganography technique than the binwalk-appended-ZIP trick — steghide embeds data *within* the image's own pixel/compression data, not just appended after it).

```bash
steghide info cute-alien.jpg
steghide extract -sf cute-alien.jpg
# Enter passphrase: alien
cat message.txt
```

![steghide extracting the hidden message](./screenshots/08_steghide_extract_message.png)

**Why the same password worked twice:** reusing `alien` (originally cracked for the ZIP) as the steghide passphrase makes sense narratively — the room is testing whether you notice a discovered password might be reused elsewhere, which is also a *very* real pattern in actual security assessments (password reuse across systems is one of the most common real findings in a pentest).

The extracted message revealed: **the SSH login password is `hackerrules!`**, signed by "chris," addressed to "james," and mentioning to "ask agent R" about the odd password choice.

### 📝 Task 3 — Questions & Answers

| Question | Answer |
|---|---|
| FTP password | **Confirmed** — `crystal` |
| Zip file password | **Confirmed** — `alien` |
| Steg password | **Confirmed** — `alien` (same password reused) |
| Who is the other agent (full name)? | *Not fully confirmed from my screenshots — the message identifies "chris" and "james" by first name only; the "full name" answer likely ties to a clue I didn't screenshot clearly* |
| SSH password | **Confirmed** — `hackerrules!` |

---

## 🚩 Task 4 — Capture the User Flag

### Logging in over SSH

```bash
ssh james@10.128.167.121
# password: hackerrules!
```

```bash
ls
cat user_flag.txt
```

![SSH login and user flag](./screenshots/11_ssh_login_user_flag.png)

**User flag:** `b03d975e8c92a7c04146cfa7a5a313c7`

Also present in the home directory: `Alien_autospy.jpg` — worth investigating further.

### Identifying the photo via reverse image search

Ran a reverse image search on `Alien_autospy.jpg` using Google Images.

![Google reverse image search results](./screenshots/09_google_reverse_image_alien_autopsy.png)

**Result:** this is a still from the infamous **"Alien Autopsy"** film released in 1995 — a well-known hoax purporting to show the dissection of an extraterrestrial recovered from the 1947 Roswell UFO incident. The footage was later exposed as a hoax created using animal organs and pig brains to fake the anatomy.

**Why this step matters as a technique, not just trivia:** reverse image search is a legitimate OSINT (Open Source Intelligence) technique — verifying the origin/authenticity of an image is a real skill used in investigations, disinformation research, and digital forensics, not just a fun CTF easter egg.

### Bonus decode along the way — CyberChef

At some point during recon, a Base64-encoded string was decoded using CyberChef:

![CyberChef decoding Base64 to "Area51"](./screenshots/10_cyberchef_base64_area51.png)

`QXJlYTUx` → decodes to → `Area51` — another thematic nod (Area 51 being the classic UFO-conspiracy location), reinforcing the room's narrative thread rather than being a strictly load-bearing clue for privilege escalation.

### 📝 Task 4 — Questions & Answers

| Question | Answer |
|---|---|
| What is the user flag? | **Confirmed** — `b03d975e8c92a7c04146cfa7a5a313c7` |
| What is the incident of the photo called? | **Confirmed** — **Alien Autopsy** (1995 hoax film) |

---

## 🔺 Task 5 — Privilege Escalation

### Checking what James can run as another user

```bash
sudo -l
```

![sudo -l output showing the (ALL, !root) restriction](./screenshots/12_sudo_l_output.png)

Result:
```
User james may run the following commands on agent-sudo:
    (ALL, !root) /bin/bash
```

**Reading this sudoers entry:** it says James can run `/bin/bash` as **any user except root** (`!root` explicitly excludes root). At first glance this looks like a safe restriction — but it's actually a well-documented vulnerability.

### The vulnerability — CVE-2019-14287

This exact `(ALL, !root)` configuration is vulnerable to **CVE-2019-14287**, a sudo bug where specifying a **user ID of `-1` or `4294967295`** (which is `-1` wrapped around as an unsigned 32-bit integer, i.e. `0xffffffff`) tricks older vulnerable versions of sudo into running the command **as root anyway** — because sudo's internal check for "is this the root user" was comparing against UID `0` specifically, and a UID that wraps around to `-1` slips past that check while still being resolved to root's actual privileges by the underlying system call.

```bash
sudo -u#$((0xffffffff)) /bin/bash
```

![Root shell obtained and root flag captured](./screenshots/13_root_shell_root_flag.png)

```
root@agent-sudo:~# whoami
root
```

Full root access obtained.

```bash
cat /root/root.txt
```

```
To Mr.hacker,

Congratulation on rooting this box. This box was designed for TryHackMe. Tips, always update your machine.

Your flag is
b53a02f55b57d4439e3341834d70c062

By,
DesKel a.k.a Agent R
```

**Root flag:** `b53a02f55b57d4439e3341834d70c062`

**Bonus answer revealed here too:** the root flag message itself is signed **"DesKel a.k.a Agent R"** — answering the room's bonus question directly.

### 📝 Task 5 — Questions & Answers

| Question | Answer |
|---|---|
| CVE number for the escalation | **Confirmed** — `CVE-2019-14287` |
| What is the root flag? | **Confirmed** — `b53a02f55b57d4439e3341834d70c062` |
| (Bonus) Who is Agent R? | **Confirmed** — **DesKel** |

---

## 🔗 Full Attack Chain Summary

```
curl with custom User-Agent → hidden announcement page → agent codename "R"
   ↓
Hydra brute-force → FTP credentials (chris:crystal)
   ↓
FTP download → cutie.png + cute-alien.jpg + To_agentJ.txt
   ↓
binwalk on cutie.png → hidden ZIP archive embedded in the file
   ↓
zip2john + John the Ripper → ZIP password cracked ("alien")
   ↓
steghide on cute-alien.jpg → same password reused → hidden message extracted
   ↓
Message reveals SSH password ("hackerrules!") for user james
   ↓
SSH foothold → user_flag.txt captured
   ↓
Reverse image search on Alien_autospy.jpg → identifies 1995 "Alien Autopsy" hoax
   ↓
sudo -l → discovers (ALL, !root) /bin/bash restriction
   ↓
CVE-2019-14287 (UID -1 / 0xffffffff bypass) → full root shell
   ↓
root.txt captured, bonus identity (DesKel a.k.a Agent R) revealed
```

---

## 🧠 Full Lessons Learned

- **Not every "protection" is a real security control.** The User-Agent gate is trivially bypassable — it's a narrative gate, not a technical one — but it's a good reminder that HTTP headers are entirely client-controlled and should never be trusted as an actual access control mechanism in real applications.
- **`binwalk` and `steghide` solve genuinely different hiding techniques.** Appending a ZIP after a PNG's real data (binwalk's target) and embedding data within the image's own compression/pixel data (steghide's target) are both "steganography" broadly, but require completely different detection and extraction tools — knowing which applies where matters.
- **Password reuse is realistic, not just a CTF shortcut.** The ZIP password and steghide passphrase being identical mirrors one of the most common real-world findings in actual penetration tests.
- **`sudo -l` should always be one of the first privilege escalation checks.** Seeing an explicit `(ALL, !root)` restriction isn't automatically safe — it's worth checking known CVEs against the exact sudo version and configuration pattern before assuming a restriction is airtight.
- **CVE-2019-14287 is a great lesson in "the fix wasn't as complete as it looked."** The `!root` exclusion *looks* like it should work, but the underlying UID-comparison logic had a gap — a good reminder that security controls need to be tested against edge cases (like negative/wrapped integers), not just the obvious direct case.
- **Reverse image search is a legitimate OSINT skill**, not just a fun detour — verifying image origin and authenticity comes up in real investigative and forensic work.

---

## 🛠️ Skills Demonstrated

`HTTP Header Manipulation` · `Hydra (Online Brute-Force)` · `FTP Enumeration` · `binwalk (File Carving)` · `zip2john + John the Ripper` · `steghide (Steganography Extraction)` · `OSINT / Reverse Image Search` · `sudo Misconfiguration Analysis` · `CVE-2019-14287 Exploitation` · `Linux Privilege Escalation`

---

## 📚 References

- [CVE-2019-14287 — NVD](https://nvd.nist.gov/vuln/detail/CVE-2019-14287)
- [binwalk — GitHub](https://github.com/ReFirmLabs/binwalk)
- [steghide Documentation](http://steghide.sourceforge.net/documentation.php)
- [Hydra — GitHub](https://github.com/vanhauser-thc/thc-hydra)
