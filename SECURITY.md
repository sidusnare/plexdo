<!--
SPDX-FileCopyrightText: 2026 SidusNare
SPDX-License-Identifier: GPL-3.0-or-later
SPDX-FileContributor: Claude Opus 5.5 (AI-generated)
-->

# Security

## Reporting a vulnerability

Please report security issues through
[GitHub's private vulnerability reporting](https://github.com/sidusnare/plexdo/security/advisories/new)
rather than a public issue.

## What this program handles

`plexdo` keeps Plex authentication tokens, and on request Plex account
passwords and Plex Home PINs. A Plex token grants access to that account's
libraries, so it is treated as a password.

- **The system keyring** holds them all: the Secret Service (GNOME Keyring,
  KWallet) on Linux and BSD, the Keychain on macOS, and Credential Manager on
  Windows, through the `keyring` package. A password is saved only by
  `plexdo login --save-password`, and `plexdo logout` removes it with the
  session it belongs to.
- **The secrets file** (`$XDG_STATE_HOME/plexdo/secrets.json`, by default
  `~/.local/state/plexdo/secrets.json`) holds them instead where there is no
  keyring, or `secret_store: file` is set. It is created readable by its owner
  alone, checked at startup, and deleted with its last secret, but it is
  **not encrypted**: anyone who can read it as you, or read a backup of it, has
  the tokens. plexdo warns each time it falls back to it unasked.
- **The configuration** (`~/.config/plexdo/config.yaml`) holds no secret. A
  password, PIN, or token found there is ignored with a warning.

Upgrading from 1.x, whose configuration held passwords in plaintext, the first
run moves every secret into the keyring and removes it from the old files.
Copies of those files made earlier, in a backup for instance, still hold them;
`plexdo logout` invalidates the tokens, but a password in an old copy stays
valid until it is changed.

## Known limitations

- `--password` on the command line is recorded in shell history and is briefly
  visible to `ps`. The value is scrubbed from the process title as early as
  possible and a warning is printed, but the exposure before that point cannot
  be eliminated. Prefer the interactive prompt.
- On Windows the scrubbing has no effect, because the technique that rewrites
  the process title has no Windows equivalent.
- A keyring unlocked for your session is readable by any program running as
  you. That is the keyring's model, not something plexdo can change.
