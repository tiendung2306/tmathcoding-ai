"""Run dashboard migrations with a MySQL lock shared by deployment processes."""
import argparse

from alembic import command
from sqlalchemy import create_engine, text
from sqlalchemy.pool import NullPool

from app.core.config import settings
from app.db.migrations import migration_config


def main():
    parser = argparse.ArgumentParser()
    commands = parser.add_subparsers(dest="action", required=True)
    for name in ("upgrade", "downgrade"):
        sub = commands.add_parser(name)
        sub.add_argument("revision")
    for name in ("current", "check", "heads", "history", "deploy"):
        commands.add_parser(name)
    revision = commands.add_parser("revision")
    revision.add_argument("--rev-id", required=True, help="YYYYMMDD_NNNN, unique in this migration chain")
    revision.add_argument("-m", "--message", required=True)
    revision.add_argument("--autogenerate", action="store_true")
    args = parser.parse_args()
    if args.action in ("heads", "history"):
        getattr(command, args.action)(migration_config())
        return
    if args.action == "revision":
        import re
        if not re.fullmatch(r"\d{8}_\d{4}", args.rev_id):
            parser.error("--rev-id must use YYYYMMDD_NNNN")
    engine = create_engine(settings.dashboard_migration_url, poolclass=NullPool)
    try:
        with engine.connect() as connection:
            lock_name = f"dashboard_migration:{settings.DASHBOARD_DB_NAME}"[:64]
            if connection.execute(text("SELECT GET_LOCK(:name, 60)"), {"name": lock_name}).scalar() != 1:
                raise RuntimeError("Another migration process holds the dashboard schema lock")
            connection.commit()
            try:
                config = migration_config(connection)
                if args.action == "deploy":
                    command.upgrade(config, "head")
                    command.check(config)
                elif args.action in ("upgrade", "downgrade"):
                    getattr(command, args.action)(config, args.revision)
                elif args.action == "revision":
                    command.revision(config, message=args.message, rev_id=args.rev_id, autogenerate=args.autogenerate)
                else:
                    getattr(command, args.action)(config)
                connection.commit()
            finally:
                connection.execute(text("SELECT RELEASE_LOCK(:name)"), {"name": lock_name})
    finally:
        engine.dispose()


if __name__ == "__main__":
    main()
