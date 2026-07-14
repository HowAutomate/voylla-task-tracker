"""
Voylla Task Tracker - mail worker.
Runs on the office server (automation-desk) where SMTP works, and delivers
every email queued in voylla.task_tracker_outbox by the web app (Render
blocks outbound SMTP, so the app can only queue).

Usage:
    python mail_worker.py           # run forever, poll every 30s
    python mail_worker.py --once    # single pass, then exit
"""
import json
import os
import platform
import sys
import time
import traceback

import psycopg2
import psycopg2.extras

if platform.system() == "Windows":
    SCRIPTS_DIR = r"C:\Users\Amit Singh\Documents\Python_Scripts"
else:
    SCRIPTS_DIR = "/home/misauto/Python_Scripts"

APP_DIR = os.path.dirname(os.path.abspath(__file__))


def find_cred(fname):
    for c in (os.path.join(APP_DIR, "creds", fname), os.path.join(SCRIPTS_DIR, fname)):
        if os.path.exists(c):
            return c
    raise FileNotFoundError(fname)


with open(find_cred("Voylla_Cred.txt")) as f:
    _l = [x.strip() for x in f.readlines()]
DB = {"host": _l[0], "user": _l[1], "password": _l[2], "database": _l[3], "port": _l[4]}

with open(find_cred("Automationalert_emailid_pass.txt")) as f:
    _m = [x.strip() for x in f.readlines()]
MAIL_USER, MAIL_PASS, MAIL_SENDER = _m[0], _m[1], _m[2]

BCC = os.environ.get("MAIL_BCC", "amit.singh@voylla.com")
OUTBOX = "voylla.task_tracker_outbox"
MAX_ATTEMPTS = 20


def process_batch():
    sent = failed = 0
    conn = psycopg2.connect(**DB)
    conn.autocommit = True
    with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
        # claim unsent mails atomically (skip rows another sender claimed <2 min ago)
        cur.execute(f"""
            UPDATE {OUTBOX} SET claimed_at = now(), attempts = attempts + 1
            WHERE id IN (
                SELECT id FROM {OUTBOX}
                WHERE sent_at IS NULL AND attempts < {MAX_ATTEMPTS}
                  AND (claimed_at IS NULL OR claimed_at < now() - interval '2 minutes')
                ORDER BY id LIMIT 20
            )
            RETURNING *
        """)
        rows = cur.fetchall()

    if rows:
        import yagmail
        yag = yagmail.SMTP({MAIL_USER: MAIL_SENDER}, MAIL_PASS)
        for r in rows:
            recips = json.loads(r["recipients"]) if r["recipients"] else None
            try:
                yag.send(to=recips or BCC, bcc=BCC if recips else None,
                         subject=r["subject"], contents=r["html"])
                with conn.cursor() as cur:
                    cur.execute(f"UPDATE {OUTBOX} SET sent_at = now() WHERE id = %s", (r["id"],))
                sent += 1
                print(f"[worker] sent #{r['id']} -> {recips}", flush=True)
            except Exception as e:
                with conn.cursor() as cur:
                    cur.execute(f"UPDATE {OUTBOX} SET last_error = %s, claimed_at = NULL WHERE id = %s",
                                (str(e)[:500], r["id"]))
                failed += 1
                print(f"[worker] FAILED #{r['id']}: {e}", flush=True)
    conn.close()
    return sent, failed


if __name__ == "__main__":
    once = "--once" in sys.argv
    print("[worker] mail worker started", flush=True)
    while True:
        try:
            s, f = process_batch()
            if s or f:
                print(f"[worker] batch done: {s} sent, {f} failed", flush=True)
        except Exception:
            traceback.print_exc()
        if once:
            break
        time.sleep(30)
