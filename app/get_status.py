"""
Python functions for creating a backup list and other info for the UI.
"""
from datetime import datetime
import multiprocessing
import os
import json
import time
import threading
import glob
import shutil
import pyzipper
import drive_requests
import dns.resolver
import google_api
import ping
import settings
import converting
import backups

def zip_file_folders(read_zip_file):
    """
    Get info of all backups stored locally.
    """
    size_json = {}
    for item in read_zip_file.infolist():
        full_path = str(item).split("=")[1].split(" ")[0]
        path = full_path.replace("backup/","",1).strip('\"').strip('\'')
        if "/" in path:
            folder_name = path.split("/")[0]
            size = str(item).split("=")[-2].split(" ")[0]
            if size.isdigit():
                try:
                    old_size = size_json[folder_name]
                except KeyError:
                    old_size = 0
                size_json[folder_name] = old_size + int(size)
        if not "/" in path and "backup/" in full_path:
            size = int(str(item).split("=")[-2].split(" ")[0])
            size_json[path] = size
    addons_json = []
    for item, value in size_json.items():
        addons_json.append({
            "name": item,
            "slug": item.lower().replace(" ", "_"),"version": False,
            "size": converting.bytes_to_human(value)
        })
    return addons_json

def list_all_drive_files():
    """
    Get info of all backups stored in Google Drive.
    """
    all_files_list = []
    for file in settings.drive_data_cache:
        if file["mimeType"] != "application/x-zip-compressed":
            continue
        addons_json = []
        for key, value in file["appProperties"].items():
            if key.replace("FOLDER_","").isdigit():
                addons_json.append(json.loads(value))
        generated_json = {
            "name": file["appProperties"]["NAME"],
            "slug": file["appProperties"]["SLUG"],
            "size": converting.bytes_to_human(file["size"]),
            "status": "Drive Only",
            "createdAt": converting.seconds_to_human(
                            time.time()-int(float(file["appProperties"]["TIMESTAMP"])),
                            True),
            "date": datetime.fromtimestamp(
                            int(float(file["appProperties"]["TIMESTAMP"]))
                            ).strftime('%a %b %m %H:%M:%S %Y'),
            "isPending": False,
            "protected": converting.str_to_bool(file["appProperties"]["PROTECTED"]),
            "type": file["appProperties"]["TYPE"],
            "folders": [],
            "addons": addons_json,
            "haVersion": False,
            "timestamp": int(float(file["appProperties"]["TIMESTAMP"])),
            "uploadable": True,
            "restorable": True,
            "status_detail": None,
            "upload_info": None,
            "ignored": False,
            "note": file["appProperties"].get("NOTE", None),
            "sources": [{
                "name": file["appProperties"]["NAME"],
                "key": "GoogleDrive",
                "size": file["size"],
                "retained": converting.str_to_bool(file["appProperties"]["RETAINED"]),
                "delete_next": False,
                "slug": file["appProperties"]["SLUG"],
                "ignored": False,
            },]
        }
        all_files_list.append(generated_json)
    all_return = list({ each['name'] : each for each in all_files_list }.values())
    settings.drive_file_list = all_return
    return all_return

def get_backup_info(file):
    """
    Get info about one backup
    """
    if not isinstance(file, str):
        return None
    filename = os.path.join(settings.BACKUP_FOLDER, file)
    if not pyzipper.is_zipfile(filename):
        return None
    with pyzipper.AESZipFile(filename, 'r', compression=pyzipper.ZIP_DEFLATED) as zip_file:
        addons_json = zip_file_folders(zip_file)
        note = zip_file.read("note.txt").decode() if "note.txt" in zip_file.namelist() else None
        backup_json_data = json.loads(zip_file.read("info.json"))
    backup_name = backup_json_data["name"]
    file_size = os.path.getsize(filename)
    generated_json = {
        "name": backup_name,
        "slug": backup_json_data["slug"],
        "size": converting.bytes_to_human(file_size),
        "status": "HA Only",
        "date": backup_json_data["creation_time"],
        "createdAt": converting.seconds_to_human(time.time()-backup_json_data["timestamp"],True),
        "isPending": False,
        "protected": backups.is_encrypted(filename),
        "type": "full" if backup_json_data["exclude_folders"] == "" else "partial",
        "folders": [],
        "addons": addons_json,
        "haVersion": False,
        "timestamp": backup_json_data["timestamp"],
        "uploadable": True,
        "restorable": True,
        "status_detail": None,
        "ignored": False,
        "note": None if len(str(note)) == 0 or note is None else str(note),
        "sources": [{
                "name": backup_json_data["name"],
                "key": "HomeAssistant",
                "size": os.path.getsize(filename),
                "retained": backups.retained_ha(backup_name),
                "delete_next": False,
                "slug": backup_json_data["slug"],
                "ignored": False,
            },]
    }
    if backup_name in settings.uploading_data_cache:
        upload_info = settings.uploading_data_cache[backup_name]
        percentage = str(int(upload_info["progress"]))
        started = converting.seconds_to_human(time.time()-upload_info["started"],True)
        generated_json["status"] = f"Uploading {percentage}%"
        generated_json["upload_info"] = {
            "name" : upload_info["name"],
            "progress": upload_info["progress"],
            "speed": upload_info["speed"],
            "total": file_size,
            "started": f"{started} ago"
        }
    for backup in settings.drive_file_list:
        if backup['name']==backup_json_data["name"]:
            if backup['slug'] == backup_json_data["slug"]:
                generated_drive = {
                    "name": backup_json_data["name"],
                    "key": "GoogleDrive",
                    "size": os.path.getsize(filename),
                    "retained": bool(backup["sources"][0]["retained"]),
                    "delete_next": False,
                    "slug": backup_json_data["slug"],
                    "ignored": False,
                }
                generated_json["sources"].append(generated_drive)
                generated_json["status"] = "Backed Up"
                generated_json["uploadable"] = False
                break
    return generated_json

def get_all_backup_info():
    """
    Get info about all backup files locally or in Google Drive.
    """
    backup_list_thread = threading.Thread(target=list_all_drive_files)
    backup_list_thread.start()
    return_loop_json = []
    desired_file_list = [file_name for file_name in os.listdir(settings.BACKUP_FOLDER)]
    backup_list_thread.join()
    with multiprocessing.Pool(processes=8) as pool:
        results = pool.map(get_backup_info, desired_file_list)
    return_loop_json = [x for x in results if x is not None]
    return_json = {}
    return_json["backups"] = settings.drive_file_list + return_loop_json
    def test(each):
        each["sources"] = list({ each['key'] : each for each in each["sources"] }.values())
        return each
    cleaned_json = list({ each['name'] : test(each) for each in return_json["backups"] }.values())
    return_json["backups"] = cleaned_json
    if settings.running_backup_info:
        return_json["backups"].append(settings.running_backup_info)
    return return_json

def ping_googleapis():
    """
    Ping all Google servers in the A record.
    """
    if isinstance(settings.googleapis_ping, dict):
        if settings.googleapis_ping["www.googleapis.com"] != "offline":
            return settings.googleapis_ping
    my_resolver = dns.resolver.Resolver()
    my_resolver.nameservers = ['8.8.8.8',"4.4.4.4"]
    ping_out = {}
    try:
        result = my_resolver.resolve('www.googleapis.com', 'A')
        result = list({ip.to_text() for ip in result})
        result.append("www.googleapis.com")
        result.append("192.123.233.32")
    except (dns.resolver.NXDOMAIN, dns.resolver.NoNameservers):
        result = []
    curr_ip = ""
    def ping_ip():
        temp_ip = curr_ip
        try:
            ping.ping(str(temp_ip), 80, 0.5).ping(1)
            ping_out[str(temp_ip)] = "alive"
        except TimeoutError:
            ping_out[str(temp_ip)] = "offline"
    try:
        for curr_ip in result:
            threading.Thread(target=ping_ip, args=()).start()
        while True:
            if len(result) == len(ping_out):
                break
            time.sleep(0.1)
    except Exception:
        ping_out[str("www.googleapis.com")] = "offline"
    settings.googleapis_ping = dict(ping_out)
    return settings.googleapis_ping

def get_bootstrap():
    """
    Collect information from all functions and combine them.
    """
    timeout = time.time() + 2
    while time.time() < timeout:
        if not settings.refresh_drive_data:
            break
        time.sleep(0.1)
    config_settings = google_api.generate_config()
    thread = threading.Thread(target = backups.last)
    thread.start()
    thread_2 = threading.Thread(target = backups.last_backup_drive)
    thread_2.start()
    backups.number_ha_retained()
    backups.last_backup_ha()
    thread_2.join()
    thread.join()
    number_ha_retained = settings.bootstrap_functions_data["number_ha_retained"]
    last_backup_ha = settings.bootstrap_functions_data["last_backup_ha"]
    last_backup_drive = settings.bootstrap_functions_data["last_backup_drive"]
    last_backup = settings.bootstrap_functions_data["last_backup"]
    number_drive_retained = drive_requests.number_drive_retained()
    count_drive = drive_requests.count_backup_drive()
    next_backup = backups.next_backup(last_backup)
    drive_backups_size = drive_requests.folder_size()
    free = shutil.disk_usage("/")[2]
    free_drive_size = settings.gdrive_info["quotaBytesTotal"]-drive_backups_size
    ping_googleapis()
    background_color = "ac="+config_settings["config"]["background_color"]
    accent_color = "bg="+config_settings["config"]["accent_color"]
    picker_url = "https://habackup.io/drive/picker"
    rest_json_config = {
        "sources": {
            "HomeAssistant": {
                "backups": len(glob.glob1(settings.BACKUP_FOLDER,"*.zip")),
                "retained": number_ha_retained,
                "deletable": len(glob.glob1(settings.BACKUP_FOLDER,"*.zip"))- number_ha_retained,
                "name": "HomeAssistant",
                "title": "Home Assistant",
                "latest": datetime.fromtimestamp(last_backup_ha).strftime('%Y-%m-%dT%H:%M:%SZ'),
                "max": config_settings["config"]["max_backups_in_ha"],
                "enabled": True,
                "icon": "home-assistant",
                "ignored": 0,
                "detail": "",
                "size": converting.bytes_to_human(google_api.backup_folder_size()),
                "ignored_size": "0 MB",
                "free_space": f"{(free // (2**30))} GB"
            },
            "GoogleDrive": {
                "backups": count_drive,
                "retained": number_drive_retained,
                "deletable": count_drive-number_drive_retained,
                "name": "GoogleDrive",
                "title": "Google Drive",
                "latest": datetime.fromtimestamp(last_backup_drive).strftime('%Y-%m-%dT%H:%M:%SZ'),
                "max": config_settings["config"]["max_backups_in_google_drive"],
                "enabled": True,
                "icon": "google-drive",
                "ignored": 0,
                "detail": settings.gdrive_info["user_email"],
                "size": converting.bytes_to_human(drive_backups_size),
                "ignored_size": "0.0 B",
                "free_space": converting.bytes_to_human(free_drive_size)
            }
        },
        "dns_info": {"www.googleapis.com": settings.googleapis_ping},
        "next_backup_text":  converting.seconds_to_human(next_backup-time.time(),True),
        "next_backup_machine": datetime.fromtimestamp(next_backup).strftime('%Y-%m-%dT%H:%M:%SZ'),
        "next_backup_detail": datetime.fromtimestamp(next_backup).strftime('%a %b %m %H:%M:%S %Y'),
        "last_backup_text": converting.seconds_to_human(time.time()-last_backup,True),
        "last_backup_machine": datetime.fromtimestamp(last_backup).strftime('%Y-%m-%dT%H:%M:%SZ'),
        "last_backup_detail": datetime.fromtimestamp(last_backup).strftime('%a %b %m %H:%M:%S %Y'),
        "backup_name_template": config_settings["config"]["backup_name"],
        "authenticate_url": settings.HABACKUP_AUTHENTICATION_URL,
        "choose_folder_url":f'{picker_url}?{background_color}&{accent_color}&version=0.108.2',
        "is_custom_creds": config_settings["is_custom_creds"],
        "folder_id": drive_requests.folder_id(),
        "is_specify_folder": config_settings["config"]["specify_backup_folder"],
        "ha_url_base": "/",
        "restore_backup_path": "hassio",
        "cred_version": 0,

        "syncing": False,
        "firstSync": False,
        "backup_cooldown_active": False,

        "last_error": None,
        "last_error_count": 0,

        "notify_check_ignored": False,
        "warn_backup_upgrade": False,
        "warn_upgrade_backups": False,
        "ask_error_reports": False,
        "warn_ingress_upgrade": False,
        "ignore_sync_error": False,
        "warn_oob_oauth": False,
        "ignore_errors_for_now": False,
        "enable_drive_upload": True
        }
    backup_name_keys = {}
    backup_name_keys["backup_name_keys"] = google_api.gen_backup_name_keys()
    backup_info = get_all_backup_info()
    return_json = { **rest_json_config, **backup_info, **backup_name_keys}
    settings.last_bootstrap_data = return_json
    return return_json
