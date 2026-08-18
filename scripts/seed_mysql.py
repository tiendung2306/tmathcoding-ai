import os
import sys
import argparse
import subprocess
import glob
from dotenv import load_dotenv

# Load .env if present in backend or root
load_dotenv(dotenv_path=os.path.join(os.path.dirname(__file__), "..", "backend", ".env"))
load_dotenv()

def seed_database(
    backup_dir: str,
    mysql_host: str,
    mysql_port: int,
    mysql_user: str,
    mysql_pass: str,
    db_name: str
):
    print("=== TMATH MYSQL AUTOMATED DATABASE SEEDER ===")
    print(f"Host             : {mysql_host}:{mysql_port}")
    print(f"Target Database  : {db_name}")
    print(f"Backup Directory : {backup_dir}")
    print("---------------------------------------------")

    abs_backup_dir = os.path.abspath(backup_dir)
    if not os.path.exists(abs_backup_dir):
        print(f"❌ Error: Backup directory '{abs_backup_dir}' does not exist.")
        print("Please check your BACKUP_DIR setting in .env or pass --backup-dir argument.")
        sys.exit(1)

    # 1. Create DB if not exists
    create_db_cmd = f"mysql -h {mysql_host} -P {mysql_port} -u {mysql_user} -p{mysql_pass} -e \"CREATE DATABASE IF NOT EXISTS {db_name} CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;\""
    print("Creating database if not exists...")
    subprocess.run(create_db_cmd, shell=True)

    # 2. Find schema files first
    schema_files = sorted(glob.glob(os.path.join(abs_backup_dir, "*-schema.sql")))
    print(f"Found {len(schema_files)} schema SQL files. Importing DDL schemas...")
    for sf in schema_files:
        cmd = f"mysql -h {mysql_host} -P {mysql_port} -u {mysql_user} -p{mysql_pass} {db_name} < \"{sf}\""
        subprocess.run(cmd, shell=True)

    # 3. Find data files
    data_files = sorted(glob.glob(os.path.join(abs_backup_dir, "*.00000.sql"))) + sorted(glob.glob(os.path.join(abs_backup_dir, "*.00001.sql")))
    print(f"Found {len(data_files)} data SQL files. Importing records...")
    for df in data_files:
        print(f"Importing {os.path.basename(df)}...")
        cmd = f"mysql -h {mysql_host} -P {mysql_port} -u {mysql_user} -p{mysql_pass} {db_name} < \"{df}\""
        subprocess.run(cmd, shell=True)

    print("\n✅ SEEDING COMPLETED SUCCESSFULLY")

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Seed tmath backup SQL files into MySQL database.")
    parser.add_argument("--backup-dir", default=os.getenv("BACKUP_DIR", "backup"), help="Directory containing backup .sql files")
    parser.add_argument("--host", default=os.getenv("MYSQL_HOST", "localhost"), help="MySQL Host")
    parser.add_argument("--port", type=int, default=int(os.getenv("MYSQL_PORT", "3306")), help="MySQL Port")
    parser.add_argument("--user", default=os.getenv("MYSQL_USER", "root"), help="MySQL User")
    parser.add_argument("--password", default=os.getenv("MYSQL_PASSWORD", "root"), help="MySQL Password")
    parser.add_argument("--db", default=os.getenv("MYSQL_DB", "dmoj"), help="MySQL Database Name")

    args = parser.parse_args()

    seed_database(
        backup_dir=args.backup_dir,
        mysql_host=args.host,
        mysql_port=args.port,
        mysql_user=args.user,
        mysql_pass=args.password,
        db_name=args.db
    )
