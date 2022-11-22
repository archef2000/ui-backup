import datetime, drive_requests, requests, backups, google_api, time, threading, settings, json

def timer_backup():
    while True:
            if backups.next() - time.time() < 5*60 and not settings.backup_running:
                backups.request()
            time.sleep(5*60)

backup_schedule = threading.Thread(target=timer_backup, name="Backup schedule")
backup_schedule.daemon = True
backup_schedule.start()

def refresh_drive_data():
    while True:
        if not settings.refresh_drive_data:
            time.sleep(5)
            continue
        headers = {
            'Authorization': 'Bearer ' + drive_requests.access_token(),
        }
        gdrive_info_request = requests.get("https://www.googleapis.com/drive/v2/about", headers=headers)
        gdrive_info = gdrive_info_request.json()
        settings.gdrive_info["user_email"] = gdrive_info["user"]["emailAddress"]
        settings.gdrive_info["quotaBytesTotal"] = int(gdrive_info["quotaBytesTotal"])
        settings.gdrive_info["quotaBytesUsed"] = int(gdrive_info["quotaBytesUsed"])
        list_files = requests.get(
        f"https://www.googleapis.com/drive/v3/files?q='{drive_requests.folder_id()}'+in+parents+and+trashed=false&supportsAllDrives=true&fields=files({settings.SELECT_FIELDS})",headers=headers)
        settings.drive_data_cache = list_files.json()["files"]
        settings.refresh_drive_data = False

backup_schedule_schedule = threading.Thread(target=refresh_drive_data, name="Drive cache", daemon = True)
backup_schedule_schedule.start()
