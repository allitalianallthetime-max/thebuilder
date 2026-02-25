"""
key_manager.py — License Key Manager CLI
==========================================
Local utility for managing Builder license keys.
Used for development, testing, and manual key operations.

Usage:
    python key_manager.py create --email user@example.com --tier pro --days 30
    python key_manager.py verify --key BUILDER-XXXX-XXXX-XXXX
    python key_manager.py list
    python key_manager.py revoke --key BUILDER-XXXX-XXXX-XXXX --reason "Expired"
    python key_manager.py stats
"""

import os
import sys
import argparse
import secrets
import psycopg2
import logging
from datetime import datetime, timedelta
from contextlib import contextmanager
from dotenv import load_dotenv

load_dotenv()

logging.basicConfig(level=logging.INFO, format="%(asctime)s [KEY-MGR] %(message)s")
log = logging.getLogger("key_manager")

DATABASE_URL = os.getenv("DATABASE_URL")

if not DATABASE_URL:
    print("ERROR: DATABASE_URL not set. Add it to .env or export it.")
    sys.exit(1)


@contextmanager
def get_db():
    conn = psycopg2.connect(DATABASE_URL)
    try:
        yield conn
    finally:
        conn.close()


def generate_license_key() -> str:
    """Generate a unique BUILDER-XXXX-XXXX-XXXX license key."""
    parts = [secrets.token_hex(2).upper() for _ in range(3)]
    return f"BUILDER-{'-'.join(parts)}"


def cmd_create(args):
    """Create a new license key directly in the database."""
    key = generate_license_key()
    expires_at = datetime.utcnow() + timedelta(days=args.days)

    with get_db() as conn:
        with conn.cursor() as cur:
            cur.execute("""
                INSERT INTO licenses
                    (license_key, email, name, status, tier, expires_at, notes)
                VALUES (%s, %s, %s, 'active', %s, %s, %s)
            """, (key, args.email, args.name, args.tier, expires_at, f"CLI created: {datetime.utcnow()}"))
            conn.commit()

    print(f"\n{'='*60}")
    print(f"  LICENSE CREATED")
    print(f"{'='*60}")
    print(f"  Key:     {key}")
    print(f"  Email:   {args.email}")
    print(f"  Name:    {args.name}")
    print(f"  Tier:    {args.tier}")
    print(f"  Expires: {expires_at.strftime('%Y-%m-%d')}")
    print(f"{'='*60}\n")


def cmd_verify(args):
    """Verify a license key exists and is active."""
    with get_db() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT status, tier, email, name, expires_at, build_count FROM licenses WHERE license_key = %s",
                (args.key,)
            )
            row = cur.fetchone()

    if not row:
        print(f"\n  ❌ License not found: {args.key}\n")
        return

    status, tier, email, name, expires_at, build_count = row
    expired = expires_at < datetime.now()

    print(f"\n{'='*60}")
    print(f"  LICENSE: {args.key}")
    print(f"{'='*60}")
    print(f"  Status:  {'🔴 EXPIRED' if expired else '🟢 ACTIVE' if status == 'active' else '⚫ ' + status.upper()}")
    print(f"  Tier:    {tier}")
    print(f"  Name:    {name}")
    print(f"  Email:   {email}")
    print(f"  Expires: {expires_at.strftime('%Y-%m-%d %H:%M')}")
    print(f"  Builds:  {build_count}")
    print(f"{'='*60}\n")


def cmd_list(args):
    """List all licenses."""
    with get_db() as conn:
        with conn.cursor() as cur:
            cur.execute("""
                SELECT license_key, email, name, status, tier, expires_at, build_count
                FROM licenses ORDER BY created_at DESC
            """)
            rows = cur.fetchall()

    if not rows:
        print("\n  No licenses found.\n")
        return

    print(f"\n{'='*100}")
    print(f"  {'KEY':<28} {'EMAIL':<28} {'TIER':<8} {'STATUS':<10} {'EXPIRES':<12} {'BUILDS'}")
    print(f"  {'-'*28} {'-'*28} {'-'*8} {'-'*10} {'-'*12} {'-'*6}")
    for r in rows:
        key, email, name, status, tier, expires_at, builds = r
        exp_str = expires_at.strftime('%Y-%m-%d') if expires_at else 'N/A'
        status_icon = '🟢' if status == 'active' else '🔴'
        print(f"  {key:<28} {email:<28} {tier:<8} {status_icon} {status:<8} {exp_str:<12} {builds}")
    print(f"{'='*100}")
    print(f"  Total: {len(rows)} licenses\n")


def cmd_revoke(args):
    """Revoke a license."""
    with get_db() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "UPDATE licenses SET status = 'revoked', notes = %s WHERE license_key = %s RETURNING email",
                (args.reason, args.key)
            )
            row = cur.fetchone()
            conn.commit()

    if row:
        print(f"\n  ✅ Revoked: {args.key} ({row[0]})")
        print(f"  Reason: {args.reason}\n")
    else:
        print(f"\n  ❌ License not found: {args.key}\n")


def cmd_stats(args):
    """Show license and build statistics."""
    with get_db() as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT COUNT(*) FROM licenses WHERE status = 'active'")
            active = cur.fetchone()[0]

            cur.execute("SELECT COUNT(*) FROM licenses")
            total_lic = cur.fetchone()[0]

            cur.execute("SELECT COUNT(*) FROM builds")
            total_builds = cur.fetchone()[0]

            cur.execute("SELECT COUNT(*) FROM builds WHERE created_at > NOW() - INTERVAL '24 hours'")
            today = cur.fetchone()[0]

            cur.execute("SELECT tier, COUNT(*) FROM licenses WHERE status = 'active' GROUP BY tier")
            tiers = dict(cur.fetchall())

    pricing = {"starter": 29, "pro": 49, "master": 99}
    mrr = sum(pricing.get(t, 49) * c for t, c in tiers.items())

    print(f"\n{'='*50}")
    print(f"  THE BUILDER — SYSTEM STATS")
    print(f"{'='*50}")
    print(f"  Licenses:  {active} active / {total_lic} total")
    print(f"  Builds:    {total_builds} total / {today} today")
    print(f"  Est. MRR:  ${mrr}")
    for tier, count in tiers.items():
        print(f"    {tier}: {count} active")
    print(f"{'='*50}\n")


def main():
    parser = argparse.ArgumentParser(
        description="The Builder — License Key Manager",
        formatter_class=argparse.RawDescriptionHelpFormatter
    )
    sub = parser.add_subparsers(dest="command", help="Command to run")

    # create
    p_create = sub.add_parser("create", help="Create a new license key")
    p_create.add_argument("--email", required=True, help="User email")
    p_create.add_argument("--name", default="Builder", help="User name")
    p_create.add_argument("--tier", default="pro", choices=["starter", "pro", "master"])
    p_create.add_argument("--days", type=int, default=30, help="Days until expiry")

    # verify
    p_verify = sub.add_parser("verify", help="Verify a license key")
    p_verify.add_argument("--key", required=True, help="License key to verify")

    # list
    sub.add_parser("list", help="List all licenses")

    # revoke
    p_revoke = sub.add_parser("revoke", help="Revoke a license")
    p_revoke.add_argument("--key", required=True, help="License key to revoke")
    p_revoke.add_argument("--reason", default="CLI revoked", help="Revocation reason")

    # stats
    sub.add_parser("stats", help="Show system statistics")

    args = parser.parse_args()

    commands = {
        "create": cmd_create,
        "verify": cmd_verify,
        "list":   cmd_list,
        "revoke": cmd_revoke,
        "stats":  cmd_stats,
    }

    if args.command in commands:
        commands[args.command](args)
    else:
        parser.print_help()


if __name__ == "__main__":
    main()
