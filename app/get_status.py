import datetime
import multiprocessing
import os
import functools
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
                except:
                    old_size = 0
                size_json[folder_name] = old_size + int(size)
        if not "/" in path and "backup/" in full_path:
            size = int(str(item).split("=")[-2].split(" ")[0])
            size_json[path] = size
    addons_json = []
    for item in size_json:
        addons_json.append({
            "name": item,
            "slug": item.lower().replace(" ", "_"),"version": False,
            "size": converting.bytes_to_human(size_json[item])
        })
    return addons_json

def list_all_drive_files():
    all_files_list = []
    for file in settings.drive_data_cache:
        if file["mimeType"] != "application/x-zip-compressed":
            continue
        addons_json = []
        for key, value in file["appProperties"].items():
            if key.replace("FOLDER_","").isdigit():
                addons_json.append(json.loads(value))
        generated_json = {}
        generated_json["name"] = file["appProperties"]["NAME"]
        generated_json["slug"] = file["appProperties"]["SLUG"]
        generated_json["size"] = converting.bytes_to_human(file["size"])
        generated_json["status"] = "Drive Only"
        generated_json["date"] = datetime.datetime.fromtimestamp(int(float(file["appProperties"]["TIMESTAMP"]))).strftime('%a %b %m %H:%M:%S %Y')
        generated_json["createdAt"] = converting.seconds_to_human(time.time()-int(float(file["appProperties"]["TIMESTAMP"])),True)
        generated_json["isPending"] = False
        generated_json["protected"] = converting.str_to_bool(file["appProperties"]["PROTECTED"])
        generated_json["type"] = file["appProperties"]["TYPE"]
        generated_json["folders"] =[] 
        generated_json["addons"] = addons_json
        generated_json["haVersion"] = False
        generated_json["timestamp"] = int(float(file["appProperties"]["TIMESTAMP"]))
        generated_json["uploadable"] = True
        generated_json["restorable"] = True
        generated_json["status_detail"] = None
        generated_json["upload_info"] = None
        generated_json["ignored"] = False
        generated_json["note"] = None if len(str(file["appProperties"]["NOTE"])) == 0 or str(file["appProperties"]["NOTE"]) == "None" else str(file["appProperties"]["NOTE"]) #None if file["appProperties"]["NOTE"] is None or "" else file["appProperties"]["NOTE"]
        generated_local = {}
        generated_local["name"] = file["appProperties"]["NAME"]
        generated_local["key"] = "GoogleDrive"
        generated_local["size"] = file["size"]
        generated_local["retained"] = converting.str_to_bool(file["appProperties"]["RETAINED"])
        generated_local["delete_next"] = False
        generated_local["slug"] = file["appProperties"]["SLUG"]
        generated_local["ignored"] = False
        generated_json["sources"] = [generated_local]
        all_files_list.append(generated_json)
    all_return = list({ each['name'] : each for each in all_files_list }.values())
    settings.drive_file_list = all_return
    return all_return

def get_backup_info(drive_file_list, file,):
    try:
        filename = os.path.join(settings.BACKUP_FOLDER, file)
    except:
        pass
    try:
        if not pyzipper.is_zipfile(filename):
            return None
    except:
        return None
    with pyzipper.AESZipFile(filename, 'r', compression=pyzipper.ZIP_DEFLATED) as read_zip_file:
        addons_json = zip_file_folders(read_zip_file)
        note = read_zip_file.read("note.txt").decode() if "note.txt" in read_zip_file.namelist() else None
        backup_json_data = json.loads(read_zip_file.read("info.json"))
    generated_json = {}
    backup_name = backup_json_data["name"]
    file_size = os.path.getsize(filename)
    generated_json["name"] = backup_name
    generated_json["slug"] = backup_json_data["slug"]
    generated_json["size"] = converting.bytes_to_human(file_size)
    generated_json["status"] = "HA Only"
    generated_json["date"] = backup_json_data["creation_time"]
    generated_json["createdAt"] = converting.seconds_to_human(time.time()-backup_json_data["timestamp"],True)
    generated_json["isPending"] = False
    generated_json["protected"] = backups.is_encrypted(filename)
    generated_json["type"] = "full" if backup_json_data["exclude_folders"] == "" else "partial"
    generated_json["folders"] =[] #[s for s in os.listdir(settings.SOURCE_FOLDER) if s not in backup_json_data["exclude_folders"] ]
    generated_json["addons"] = addons_json
    generated_json["haVersion"] = False
    generated_json["timestamp"] = backup_json_data["timestamp"]
    generated_json["uploadable"] = True
    generated_json["restorable"] = True
    generated_json["status_detail"] = None
    if backup_name in settings.uploading_data_cache:
        upload_info = settings.uploading_data_cache[backup_name]
        percentage = str(upload_info["progress"]).split(".")[0]
        started = converting.seconds_to_human(time.time()-upload_info["started"],True)
        generated_json["status"] = f"Uploading {percentage}%"
        generated_json["upload_info"] = {
            "name" : upload_info["name"],
            "progress": upload_info["progress"], # %
            "speed": upload_info["speed"], # bytes/second
            "total": file_size, # size of file
            "started": f"{started} ago"
        }
    generated_json["ignored"] = False
    generated_json["note"] = None if len(str(note)) == 0 or note == None else str(note)
    generated_local = {}
    generated_local["name"] = backup_json_data["name"]
    generated_local["key"] = "HomeAssistant"
    generated_local["size"] = os.path.getsize(filename)
    generated_local["retained"] = backups.retained_ha(backup_name)
    generated_local["delete_next"] = False
    generated_local["slug"] = backup_json_data["slug"]
    generated_local["ignored"] = False
    generated_json["sources"] = []
    for a in drive_file_list:
        if a['name']==backup_json_data["name"]:
            if a['slug'] == backup_json_data["slug"] and 0 ==0:
                generated_drive = {}
                generated_drive["name"] = backup_json_data["name"]
                generated_drive["key"] = "GoogleDrive"
                generated_drive["size"] = os.path.getsize(filename)
                generated_drive["retained"] = bool(a["sources"][0]["retained"])
                generated_drive["delete_next"] = False
                generated_drive["slug"] = backup_json_data["slug"]
                generated_drive["ignored"] = False
                generated_json["sources"].append(generated_drive) 
                generated_json["status"] = "Backed Up"
                generated_json["uploadable"] = False    
    generated_json["sources"].append(generated_local)
    return generated_json

def get_all_backup_info():
    x = threading.Thread(target=list_all_drive_files)
    x.start()
    return_loop_json = []
    desired_file_list = [file_name for file_name in os.listdir(settings.BACKUP_FOLDER)]
    x.join()
    with multiprocessing.Pool(processes=8) as pool:
        results = pool.map(functools.partial(get_backup_info,settings.drive_file_list), desired_file_list)
    return_loop_json = [x for x in results if x != None]
    return_json = {}
    return_json["backups"] = settings.drive_file_list
    for x in return_loop_json:
        return_json["backups"].append(x)
    def test(each):
        each["sources"] = list({ each['key'] : each for each in each["sources"] }.values())
        return each
    return_json["backups"] = list({ each['name'] : test(each) for each in list(return_json["backups"]) }.values())
    if len(str(settings.running_backup_info)) >= 3:
        return_json["backups"].append(settings.running_backup_info)
    return return_json

def ping_googleapis():
    if type(settings.www_googleapis_com_ping_out) is dict:
        if settings.www_googleapis_com_ping_out["dns_info"]["www.googleapis.com"]["www.googleapis.com"] != "offline" or 1==1:
            return settings.www_googleapis_com_ping_out
    my_resolver = dns.resolver.Resolver()
    my_resolver.nameservers = ['8.8.8.8',"4.4.4.4"]
    ping_out = {}
    try:
        result = my_resolver.resolve('www.googleapis.com', 'A')
        result = list({ip.to_text() for ip in result})
        result.append("www.googleapis.com")
    except:
        result = []
    ip = ""
    def ping_ip():
        temp_ip = ip
        try:
            ping.ping(str(temp_ip), 80, 0.5).ping(1)    
            ping_out[str(temp_ip)] = "alive"
        except:
            ping_out[str(temp_ip)] = "offline"
    try:
        for ip in result:
            threading.Thread(target=ping_ip, args=()).start()
        while True:
            if len(result) == len(ping_out):
                break
            time.sleep(0.1)
    except:
        ping_out[str("www.googleapis.com")] = "offline"
    settings.www_googleapis_com_ping_out = {}
    settings.www_googleapis_com_ping_out["dns_info"] = {}
    settings.www_googleapis_com_ping_out["dns_info"]["www.googleapis.com"] = dict(ping_out)
    return settings.www_googleapis_com_ping_out

def get_bootstrap():
    timeout = time.time() + 2
    while time.time() < timeout:
        if not settings.refresh_drive_data: break
        time.sleep(0.1)
    config_settings = google_api.generate_config() # 0,03
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
    drive_retained = drive_requests.drive_retained() # 0
    count_drive = drive_requests.count_backup_drive() # 0
    next_backup = backups.next(last_backup) # 0,002
    drive_backups_size = drive_requests.folder_size()
    free = shutil.disk_usage("/")[2] # 0
    rest_json_config = {
        "sources": {
            "HomeAssistant": {
                "backups": len(glob.glob1(settings.BACKUP_FOLDER,"*.zip")),
                "retained": number_ha_retained,
                "deletable": len(glob.glob1(settings.BACKUP_FOLDER,"*.zip"))- number_ha_retained,
                "name": "HomeAssistant",
                "title": "Home Assistant",
                "latest": datetime.datetime.fromtimestamp(last_backup_ha).strftime('%Y-%m-%dT%H:%M:%SZ'),
                "max": config_settings["config"]["max_backups_in_ha"],
                "enabled": True,
                "icon": "home-assistant",
                "ignored": 0,
                "detail": "",
                "size": converting.bytes_to_human(google_api.backup_folder_size()), # 0,05
                "ignored_size": "0 MB",
                "free_space": f"{(free // (2**30))} GB"
            },
            "GoogleDrive": {
                "backups": count_drive,
                "retained": drive_retained,
                "deletable": count_drive-drive_retained,
                "name": "GoogleDrive",
                "title": "Google Drive",
                "latest": datetime.datetime.fromtimestamp(last_backup_drive).strftime('%Y-%m-%dT%H:%M:%SZ'),
                "max": config_settings["config"]["max_backups_in_google_drive"],
                "enabled": True,
                "icon": "google-drive",
                "ignored": 0,
                "detail": settings.gdrive_info["user_email"],
                "size": converting.bytes_to_human(drive_backups_size),
                "ignored_size": "0.0 B",
                "free_space": converting.bytes_to_human(settings.gdrive_info["quotaBytesTotal"]-drive_backups_size)
            }
        },
        "next_backup_text":  converting.seconds_to_human(next_backup-time.time(),True),
        "next_backup_machine": datetime.datetime.fromtimestamp(next_backup).strftime('%Y-%m-%dT%H:%M:%SZ'),
        "next_backup_detail": datetime.datetime.fromtimestamp(next_backup).strftime('%a %b %m %H:%M:%S %Y'),
        "last_backup_text": converting.seconds_to_human(time.time()-last_backup,True),
        "last_backup_machine": datetime.datetime.fromtimestamp(last_backup).strftime('%Y-%m-%dT%H:%M:%SZ'),
        "last_backup_detail": datetime.datetime.fromtimestamp(last_backup).strftime('%a %b %m %H:%M:%S %Y'),
        "backup_name_template": config_settings["config"]["backup_name"],
        "authenticate_url": settings.HABACKUP_AUTHENTICATION_URL,
        "choose_folder_url": f'https://habackup.io/drive/picker?bg={config_settings["config"]["background_color"]}&ac={config_settings["config"]["accent_color"]}&version=0.108.2',
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
        "warn_backup_upgrade": False, #
        "warn_upgrade_backups": False,#
        "ask_error_reports": False,
        "warn_ingress_upgrade": False,
        "ignore_sync_error": False,
        "warn_oob_oauth": False,
        "ignore_errors_for_now": False,
        "enable_drive_upload": True
        } # 0.002
    backup_name_keys = {}
    backup_name_keys["backup_name_keys"] = google_api.gen_backup_name_keys() # 0 sec
    ping_google = ping_googleapis() # 1.1 start
    backup_info = get_all_backup_info() # 0,08 sec
    return_json = { **rest_json_config, **ping_google, **backup_info, **backup_name_keys}
    settings.last_bootstrap_data = return_json
    return return_json