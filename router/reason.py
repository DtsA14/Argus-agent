"""The human's typed reason (SPEC_CHAT_T4A 10 item 4): one line of 10..500 characters, refused (never cut) otherwise, and never a key. One rule for
`argus apply --accept-concerns` (it goes to a commit message) and `argus queue go --reason-file` (it goes to the queue), so the two cannot drift."""
import json
import unicodedata

from codetask import examples as ex
from router import job as rj
from router import stage_data

MIN, MAX = 10, 500


def check(text, flag, tail="nothing was changed"):
    """The reason as it will be stored. flag: the option that carried it (named in the refusal); tail: what the refusal says was not done."""
    if not isinstance(text, str) or any(unicodedata.category(c)[0] == "C" for c in text):
        raise rj.Refused(f"{flag}: the reason must be plain text without control characters; {tail}")
    t = ex.clean(text, 10_000)
    if not MIN <= len(t) <= MAX:
        raise rj.Refused(f"{flag}: the reason must be {MIN} to {MAX} characters (it has {len(t)}); {tail}")
    if stage_data.KEY.search(t.encode()) or stage_data.KEY.search(json.dumps(t).encode()):
        raise rj.Refused(f"{flag}: the reason looks like it holds a key or a secret; it must not reach git history; {tail}")
    return t
