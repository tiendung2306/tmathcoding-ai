"""One-time verified copy. Never changes or drops tables in the source database."""
import argparse
import re

from sqlalchemy import MetaData, Table, create_engine, inspect
from sqlalchemy.pool import NullPool

from app.core.config import settings
from app.core.dashboard_database import DashboardBase
from app.db.data_transfer import copy_table
import app.models.dashboard


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--apply", action="store_true", help="Default is a read-only row count preview")
    parser.add_argument("--legacy-config-db", help="Old class_star DB on the source server")
    args = parser.parse_args()
    if args.legacy_config_db and not re.fullmatch(r"[A-Za-z0-9_]{1,64}", args.legacy_config_db):
        parser.error("Invalid legacy database name")
    source_engine = create_engine(settings.source_database_url.set(drivername="mysql+pymysql"), poolclass=NullPool)
    target_engine = create_engine(settings.dashboard_migration_url, poolclass=NullPool)
    try:
        with source_engine.connect() as source, target_engine.begin() as target:
            for name in ("tmath_virtual_class_session", "judge_problem_ai_tag"):
                if inspect(source).has_table(name):
                    table = Table(name, MetaData(), autoload_with=source, resolve_fks=False)
                    count = copy_table(source, target, table, DashboardBase.metadata.tables[name], apply=args.apply)
                    print(f"{name}: {count} rows {'copied and verified' if args.apply else 'to copy'}")
        if args.legacy_config_db:
            legacy_engine = create_engine(source_engine.url.set(database=args.legacy_config_db), poolclass=NullPool)
            try:
                with legacy_engine.connect() as source, target_engine.begin() as target:
                    if inspect(source).has_table("class_star"):
                        table = Table("class_star", MetaData(), autoload_with=source, resolve_fks=False)
                        count = copy_table(source, target, table, DashboardBase.metadata.tables["class_star"], apply=args.apply)
                        print(f"class_star: {count} rows {'copied and verified' if args.apply else 'to copy'}")
            finally:
                legacy_engine.dispose()
    finally:
        source_engine.dispose()
        target_engine.dispose()


if __name__ == "__main__":
    main()
