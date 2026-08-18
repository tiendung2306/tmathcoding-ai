import os
import sys
import subprocess
import glob

def seed_database(backup_dir: str, mysql_user: str = "root", mysql_pass: str = "root", db_name: str = "dmoj"):
    print(f"=== TMATH MYSQL AUTOMATED DATABASE SEEDER ===")
    print(f"Backup Directory: {backup_dir}")
    print(f"Target Database: {db_name}")

    if not os.path.exists(backup_dir):
        print(f"Error: Backup directory '{backup_dir}' does not exist.")
        sys.exit(1)

    # 1. Create DB if not exists
    create_db_cmd = f"mysql -u {mysql_user} -p{mysql_pass} -e \"CREATE DATABASE IF NOT EXISTS {db_name} CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;\""
    print("Creating database if not exists...")
    subprocess.run(create_db_cmd, shell=True)

    # 2. Find schema files first
    schema_files = sorted(glob.glob(os.path.join(backup_dir, "*-schema.sql")))
    print(f"Found {len(schema_files)} schema SQL files. Importing DDL schemas...")
    for sf in schema_files:
        cmd = f"mysql -u {mysql_user} -p{mysql_pass} {db_name} < \"{sf}\""
        subprocess.run(cmd, shell=True)

    # 3. Find data files
    data_files = sorted(glob.glob(os.path.join(backup_dir, "*.00000.sql"))) + sorted(glob.glob(os.path.join(backup_dir, "*.00001.sql")))
    print(f"Found {len(data_files)} data SQL files. Importing records...")
    for df in data_files:
        print(f"Importing {os.path.basename(df)}...")
        cmd = f"mysql -u {mysql_user} -p{mysql_pass} {db_name} < \"{df}\""
        subprocess.run(cmd, shell=True)

    print("=== SEEDING COMPLETED SUCCESSFULLY ===")

if __name__ == "__main__":
    backup_path = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "backup"))
    seed_database(backup_path)
