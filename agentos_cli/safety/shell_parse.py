"""Shell argv parsing helpers.

`parse_shell_string(s)` returns a tokenized argv list when the input is a safe,
simple command (no operators, no expansion, no redirection, balanced quotes).
Returns ``None`` to signal that the string contains constructs we will not
attempt to statically evaluate — callers MUST treat ``None`` as
"unsafe — must prompt" and route the command through user approval.

The intent here is *conservative deny*, not a complete shell. If shlex cannot
trivially tokenize the input, or if any wrapper/operator character appears,
we refuse to vouch for it.
"""
from __future__ import annotations

import shlex
from typing import Optional

# Characters/sequences that indicate the input is more than a single program
# invocation and therefore must be escalated to user prompt regardless of any
# allow-listed pattern.
_UNSAFE_SUBSTRINGS: tuple[str, ...] = (
    "$(",   # command substitution
    "`",    # command substitution (backticks)
    "&&",   # logical and
    "||",   # logical or
    ";",    # statement separator
    "|",    # pipe
    ">",    # output redirection
    "<",    # input redirection / heredoc start
    "&",    # background / fd duplication
    "\n",   # multi-line script
    "\r",   # CRLF script
)


def looks_unsafe(s: str) -> bool:
    """Return True if `s` contains any shell metacharacter we refuse to parse."""
    if not isinstance(s, str):
        return True
    for token in _UNSAFE_SUBSTRINGS:
        if token in s:
            return True
    return False


def parse_shell_string(s: str) -> Optional[list[str]]:
    """Try to tokenize `s` as a simple argv list.

    Returns:
        list[str]: tokenized argv when input is a single safe command.
        None: when input contains shell operators, substitution, redirection,
              unmatched quotes, or otherwise fails to parse trivially.
              Callers MUST escalate to user approval.
    """
    if s is None:
        return None
    if not isinstance(s, str):
        return None
    stripped = s.strip()
    if not stripped:
        return None
    if looks_unsafe(stripped):
        return None
    try:
        # posix=True with no comments/expansion. Raises ValueError on
        # unmatched quotes.
        tokens = shlex.split(stripped, comments=False, posix=True)
    except ValueError:
        return None
    if not tokens:
        return None
    return tokens
