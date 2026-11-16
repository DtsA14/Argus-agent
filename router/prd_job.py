"""A job of kind "prd" (docs/reviews/SPEC_PRD_WRITER.md section 4): a conversation with the PRD writer.

This file holds what the router needs to know about the kind (its states and legal moves, and the dispatch points in
router/job.py); the writer's turn, the gate and the folder come with the next change (SPEC_PRD_WRITER 9, PR 2).

  NEW -> WRITING (wN) -> AWAITING_HUMAN -> WRITING (reply) -> ... ; WRITING -> WRITE_FAILED (a reply tries again)
  BLOCKED when a turn cannot be funded, the repository's state refuses it or the provider fails; every state but
  ABANDONED -> ABANDONED. There is no HANDED_OFF and no "approved": `argus prd approve` makes a queue from a folder and
  leaves the job as it is (it can still be replied to).
"""
from . import issue as ri
from . import job as rj

NEW, WRITING, AWAITING_HUMAN, WRITE_FAILED = rj.NEW, ri.WRITING, ri.AWAITING_HUMAN, ri.WRITE_FAILED
BLOCKED, ABANDONED = rj.BLOCKED, rj.ABANDONED
SECTION = "prd_writer"          # the config section that holds the writer's role, caps and limits
LEGAL = {(NEW, WRITING), (NEW, BLOCKED), (WRITING, AWAITING_HUMAN), (WRITING, WRITE_FAILED), (WRITING, BLOCKED),
         (AWAITING_HUMAN, WRITING), (WRITE_FAILED, WRITING)} | \
        {(s, ABANDONED) for s in (NEW, WRITING, AWAITING_HUMAN, WRITE_FAILED, BLOCKED)}
REPLYABLE = (AWAITING_HUMAN, WRITE_FAILED)


def resume(job, cfg, deps):
    """Continue the turn a crash interrupted. The turn itself is not built yet (SPEC_PRD_WRITER 9, PR 2)."""
    raise rj.Refused(f"job {job.id}: the PRD writer's turn is not built yet; nothing was resumed")


def status_lines(job):
    """The PRD job for `argus status`: where it is (PR 2 adds the folder, the touches and the check line)."""
    i = job.data.get("inputs") or {}
    return [f"repository {i.get('repo_name')} at {str(i.get('commit'))[:12]}, environment {i.get('environment')}"]
