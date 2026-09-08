import os
import sys
import argparse
import subprocess
import glob
from dotenv import load_dotenv

# Load .env if present in backend or root
load_dotenv(dotenv_path=os.path.join(os.path.dirname(__file__), "..", "backend", ".env"))
load_dotenv(dotenv_path=os.path.join(os.path.dirname(__file__), "..", ".env"))
load_dotenv()

def find_backup_dir(requested_path: str) -> str:
    possible_paths = [
        requested_path,
        os.path.abspath(requested_path),
        "/app/backup",
        "/backup",
        os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "backup")),
    ]
    for path in possible_paths:
        if path and os.path.exists(path) and os.path.isdir(path):
            return os.path.abspath(path)
    return os.path.abspath(requested_path)

def stream_import_sql(file_path: str, mysql_host: str, mysql_port: int, mysql_user: str, db_name: str, env: dict):
    cmd = [
        "mysql",
        "-h", mysql_host,
        "-P", str(mysql_port),
        "-u", mysql_user,
        "--skip-ssl",
        "--default-character-set=utf8mb4",
        db_name
    ]
    proc = subprocess.Popen(cmd, stdin=subprocess.PIPE, env=env)
    
    # Read and stream line by line replacing deprecated MySQL 8.0 sql_mode
    with open(file_path, "rb") as f:
        for line in f:
            if b"NO_AUTO_CREATE_USER" in line:
                line = line.replace(b"NO_AUTO_CREATE_USER,", b"").replace(b",NO_AUTO_CREATE_USER", b"").replace(b"NO_AUTO_CREATE_USER", b"")
            proc.stdin.write(line)
            
    proc.stdin.close()
    return proc.wait()

def seed_database(
    backup_dir: str,
    mysql_host: str,
    mysql_port: int,
    mysql_user: str,
    mysql_pass: str,
    db_name: str
):
    # Auto-adjust host if running inside Docker container and host is localhost
    if (mysql_host in ["localhost", "127.0.0.1"]) and os.path.exists("/.dockerenv"):
        mysql_host = "db"

    abs_backup_dir = find_backup_dir(backup_dir)

    print("=== TMATH MYSQL AUTOMATED DATABASE SEEDER ===")
    print(f"Host             : {mysql_host}:{mysql_port}")
    print(f"Target Database  : {db_name}")
    print(f"Backup Directory : {abs_backup_dir}")
    print("---------------------------------------------")

    if not os.path.exists(abs_backup_dir):
        print(f"❌ Error: Backup directory '{abs_backup_dir}' does not exist.")
        print("Please check your BACKUP_DIR setting in .env or pass --backup-dir argument.")
        sys.exit(1)

    env = os.environ.copy()
    if mysql_pass:
        env["MYSQL_PWD"] = mysql_pass

    # 1. Create DB if not exists
    print(f"Creating database '{db_name}' if not exists...")
    create_db_cmd = [
        "mysql",
        "-h", mysql_host,
        "-P", str(mysql_port),
        "-u", mysql_user,
        "--skip-ssl",
        "-e", f"CREATE DATABASE IF NOT EXISTS `{db_name}` CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;"
    ]
    res = subprocess.run(create_db_cmd, env=env)
    if res.returncode != 0:
        print(f"❌ Error creating database '{db_name}'. Exit code: {res.returncode}")
        sys.exit(res.returncode)

    # 2. Find schema files first
    all_sql_files = glob.glob(os.path.join(abs_backup_dir, "*.sql"))
    schema_files = sorted([f for f in all_sql_files if f.endswith("-schema.sql")])
    
    print(f"Found {len(schema_files)} schema SQL files. Importing DDL schemas...")
    for sf in schema_files:
        code = stream_import_sql(sf, mysql_host, mysql_port, mysql_user, db_name, env)
        if code != 0:
            print(f"⚠️ Warning: Schema file {os.path.basename(sf)} returned exit code {code}")

    # 3. Find data files (all sql files except schemas and create-db)
    data_files = sorted([
        f for f in all_sql_files 
        if not f.endswith("-schema.sql") and not os.path.basename(f).startswith("dmoj-schema-create")
    ])
    
    print(f"Found {len(data_files)} data SQL files. Importing records...")
    for df in data_files:
        print(f"Importing {os.path.basename(df)}...")
        code = stream_import_sql(df, mysql_host, mysql_port, mysql_user, db_name, env)
        if code != 0:
            print(f"⚠️ Warning: Data file {os.path.basename(df)} returned exit code {code}")

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
