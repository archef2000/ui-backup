"""
Only used for updating the drive cache and a timer for backup creation.
"""
import os
import time
import threading
import urllib.parse
import requests
import settings
import drive_requests
import backups

def timer_backup():
    """
    Checks if a backup is due.
    """
    while True:
        if not os.path.exists(os.path.join(settings.DATA_FOLDER ,"credentials.dat")):
            time.sleep(5)
            continue
        if backups.next_backup() - time.time() < 5*60 and not settings.backup_running:
            backups.request()
        time.sleep(5*60)

backup_schedule = threading.Thread(target=timer_backup, name="Backup schedule",daemon=True)
backup_schedule.start()

def refresh_drive_data():
    """
    Updates to data on Google Drive.
    """
    while True:
        credentials_exist = os.path.exists(os.path.join(settings.DATA_FOLDER ,"credentials.dat"))
        if not settings.refresh_drive_data or not credentials_exist:
            time.sleep(5)
            continue
        headers = {
            'Authorization': 'Bearer ' + drive_requests.access_token(),
        }
        gdrive_info_request = requests.get(
                        "https://www.googleapis.com/drive/v2/about",
                        headers=headers, timeout=10)
        gdrive_info = gdrive_info_request.json()
        settings.gdrive_info["user_email"] = gdrive_info["user"]["emailAddress"]
        settings.gdrive_info["quotaBytesTotal"] = int(gdrive_info["quotaBytesTotal"])
        settings.gdrive_info["quotaBytesUsed"] = int(gdrive_info["quotaBytesUsed"])
        query_json = {
            "supportsAllDrives": "true",
        }
        query = f"q='{drive_requests.folder_id()}'+in+parents+and+trashed=false"
        query += f"&fields=files({settings.SELECT_FIELDS})"
        query += f"&{urllib.parse.urlencode(query_json)}"
        list_files = requests.get(
        f"https://www.googleapis.com/drive/v3/files?{query}",
            headers=headers, timeout=10)
        settings.drive_data_cache = list_files.json()["files"]
        settings.refresh_drive_data = False

backup_schedule_schedule = threading.Thread(target=refresh_drive_data,daemon=True)
backup_schedule_schedule.start()

def create_dir(dir):
    if not os.path.exists(dir):
        os.makedirs(dir)

def first_setup():
    create_dir(settings.BACKUP_FOLDER)
    create_dir(settings.SOURCE_FOLDER)
    create_dir(settings.DATA_FOLDER)

first_setup()