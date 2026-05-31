import os
import tarfile
from datetime import UTC, datetime
from pathlib import Path

import boto3
from dotenv import load_dotenv

load_dotenv(Path(__file__).resolve().parent.parent.parent / ".env")


def get_r2_client():
    return boto3.client(
        "s3",
        endpoint_url=os.getenv("R2_ENDPOINT"),
        aws_access_key_id=os.getenv("R2_ACCESS_KEY_ID"),
        aws_secret_access_key=os.getenv("R2_SECRET_ACCESS_KEY"),
        region_name="auto",
    )


def upload_to_clouds(filepath, key_prefix=""):
    client = get_r2_client()
    bucket = os.getenv("R2_BUCKET")
    filename = Path(filepath).name
    timestamp = datetime.now(UTC).strftime("%Y%m%d_%H%M")
    key = f"{key_prefix}/{timestamp}_{filename}"

    # 1. R2 Upload
    try:
        client.upload_file(str(filepath), bucket, key)
        print(f"Uploaded to R2: {key}")
    except Exception as e:
        print(f"R2 Upload Error: {e}")

    # 2. rclone GDrive Upload
    import subprocess

    rclone_dest = f"Cipher:cipher-backups/{key}"
    try:
        subprocess.run(
            ["rclone", "copyto", str(filepath), rclone_dest],
            check=True,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
        print(f"Uploaded to GDrive: {rclone_dest}")
    except Exception as e:
        print(f"GDrive Upload Error: {e}")

    return key


def backup_sqlite_databases():
    # Detect all sqlite files in user_data/
    user_data_dir = Path(__file__).resolve().parent.parent.parent / "user_data"
    paths = list(user_data_dir.glob("*.sqlite"))

    # Also include the specific one mentioned in the request if not captured
    specific_path = user_data_dir / "tradesv3.sqlite"
    if specific_path.exists() and specific_path not in paths:
        paths.append(specific_path)

    for path in paths:
        if path.exists():
            upload_to_clouds(path, "databases")


def backup_chromadb():
    vault_dir = Path(__file__).resolve().parent.parent / "vault/chroma_db"
    if not vault_dir.exists():
        print("ChromaDB vault not found, skipping.")
        return

    archive = "/tmp/chromadb_backup.tar.gz"
    with tarfile.open(archive, "w:gz") as tar:
        tar.add(vault_dir, arcname="chroma_db")

    upload_to_clouds(archive, "vault")
    os.remove(archive)


def backup_models():
    # Oracle models
    model_files = [
        Path(__file__).resolve().parent.parent / "oracle/hmm_model.pkl",
    ]
    for path in model_files:
        if path.exists():
            upload_to_clouds(path, "models")

    # FreqAI models directory
    freqai_dir = Path(__file__).resolve().parent.parent.parent / "user_data/models"
    if freqai_dir.exists():
        archive = "/tmp/freqai_models.tar.gz"
        with tarfile.open(archive, "w:gz") as tar:
            tar.add(freqai_dir, arcname="freqai_models")
        upload_to_clouds(archive, "models")
        os.remove(archive)


def backup_constraints():
    constraints_dir = Path(__file__).resolve().parent.parent / "vault/constraints"
    if constraints_dir.exists():
        archive = "/tmp/constraints.tar.gz"
        with tarfile.open(archive, "w:gz") as tar:
            tar.add(constraints_dir, arcname="constraints")
        upload_to_clouds(archive, "vault")
        os.remove(archive)


def list_backups():
    client = get_r2_client()
    bucket = os.getenv("R2_BUCKET")
    try:
        response = client.list_objects_v2(Bucket=bucket)
        files = response.get("Contents", [])
        print(f"\nR2 Backup Contents ({len(files)} files):")
        for f in sorted(files, key=lambda x: x["LastModified"], reverse=True)[:20]:
            size_mb = f["Size"] / 1024 / 1024
            print(f"  {f['Key']} ({size_mb:.1f} MB)")
    except Exception as e:
        print(f"Error listing backups: {e}")


def restore_latest_sqlite():
    client = get_r2_client()
    bucket = os.getenv("R2_BUCKET")

    try:
        response = client.list_objects_v2(Bucket=bucket, Prefix="databases/")
        files = sorted(response.get("Contents", []), key=lambda x: x["LastModified"], reverse=True)

        if files:
            latest = files[0]["Key"]
            print(f"Restoring: {latest}")
            restore_path = str(
                Path(__file__).resolve().parent.parent.parent / "user_data/tradesv3_restored.sqlite"
            )
            client.download_file(bucket, latest, restore_path)
            print(f"Restored to {restore_path}")
            print("Rename manually to tradesv3.sqlite after verification")
        else:
            print("No SQLite backups found in R2")
    except Exception as e:
        print(f"Error restoring SQLite: {e}")


def run_full_backup():
    print("Starting R2 backup...")
    results = []

    try:
        backup_sqlite_databases()
        results.append("✅ SQLite databases")
    except Exception as e:
        results.append(f"❌ SQLite: {e}")

    try:
        backup_chromadb()
        results.append("✅ ChromaDB Vault")
    except Exception as e:
        results.append(f"❌ ChromaDB: {e}")

    try:
        backup_models()
        results.append("✅ ML Models (HMM + FreqAI)")
    except Exception as e:
        results.append(f"❌ Models: {e}")

    try:
        backup_constraints()
        results.append("✅ Vault Constraints")
    except Exception as e:
        results.append(f"❌ Constraints: {e}")

    print("\nBackup Summary:")
    for r in results:
        print(f"  {r}")

    return results


if __name__ == "__main__":
    run_full_backup()
