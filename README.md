# CTF Writeups

![Writeups](https://img.shields.io/badge/Writeups-Growing-38BDF8?style=flat-square)
![Categories](https://img.shields.io/badge/Categories-11-0EA5E9?style=flat-square)
![Author](https://img.shields.io/badge/Author-Aymwvn-0284C7?style=flat-square)

Personal archive of CTF challenges I've solved, organized by category. Each writeup follows a consistent methodology: recon → analysis → exploitation → flag, with tools and reasoning documented so the approach is reusable, not just the answer.

Maintained by **[Aymane Boualam (Aymwvn)](https://github.com/Aymwvn)** — Cybersecurity Analyst & Penetration Tester.

---

## Why this repo exists

CTFs are how I sharpen offensive security skills outside of school and internship work. This repo is:
- A personal knowledge base I can search when I hit a familiar pattern again
- Proof of consistent, active skill-building across categories (not just one specialty)
- A reference for anyone else working through similar challenges

---

## Categories

| Category | Focus | Count |
|---|---|---|
| [Web](./web) | SQLi, XSS, SSRF, IDOR, auth bypass, deserialization | - |
| [Crypto](./crypto) | Classical ciphers, RSA attacks, hash length extension | - |
| [Reverse Engineering](./reverse-engineering) | Static/dynamic analysis, disassembly, unpacking | - |
| [Pwn](./pwn) | Buffer overflows, ROP chains, format strings | - |
| [Network](./network) | Packet analysis, protocol abuse, traffic reconstruction | - |
| [OSINT](./osint) | Metadata, geolocation, social recon, image/EXIF analysis | - |
| [Forensics / DFIR](./forensics-dfir) | Memory dumps, disk images, log analysis, timeline reconstruction | - |
| [Steganography](./steganography) | Hidden data in images, audio, files | - |
| [Misc](./misc) | Anything that doesn't fit elsewhere — logic puzzles, esoteric formats | - |
| [AI](./ai) | Prompt injection, model extraction, adversarial challenges | - |
| [Hardware](./hardware) | Firmware analysis, embedded systems, side-channel basics | - |

*(Count column updates as writeups get added — keep it honest, don't inflate.)*

---

## Methodology

Every writeup in this repo follows the same structure (see [`TEMPLATE.md`](./TEMPLATE.md)):

1. **Challenge Info** — name, category, difficulty, points, CTF event
2. **Recon** — what I gathered before touching the actual vulnerability
3. **Analysis** — what I noticed, what hypothesis I formed
4. **Exploitation** — exact steps taken, commands used, why they worked
5. **Flag**
6. **Lessons Learned** — what I'd do faster next time, what concept this reinforced

This isn't just "here's the flag" — it's designed to show reasoning, which matters more to anyone reviewing this repo (recruiters, admissions committees, other players) than the answer itself.

---

## How to use this repo

- Browse by category folder above
- Each writeup lives in its own subfolder: `category/event-name_challenge-name/README.md`
- Screenshots/scripts used during solving go in the same subfolder
- Use [`TEMPLATE.md`](./TEMPLATE.md) as the starting point for any new writeup

---

## Connect

- Portfolio: [aymwvn.me](https://aymwvn.me)
- LinkedIn: [aymane-boualam](https://linkedin.com/in/aymane-boualam/)
- GitHub: [@Aymwvn](https://github.com/Aymwvn)
