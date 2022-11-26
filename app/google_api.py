import converting
import os
import datetime
import json
import settings
import socket
import pyzipper
import drive_requests

def get_folder():
    return_slug = []
    source_dir_list = os.listdir(settings.SOURCE_FOLDER)
    for item in source_dir_list:
        loop_json = {}
        loop_json["slug"] = item
        loop_json["id"] = item
        loop_json["name"] = item
        if os.path.isfile(os.path.join(settings.SOURCE_FOLDER, item)):
            path_type = "File"
        else:
            path_type = "Folder"
        loop_json["description"] = f"{path_type} named {item}"
        return_slug.append(loop_json)
    if os.path.isfile(os.path.join(settings.DATA_FOLDER,"options.json")):
        exclude_list = list(json.load(open(os.path.join(settings.DATA_FOLDER,"options.json"),encoding="utf-8")).get("exclude_folders","").split(","))
        for item in exclude_list:
            if not item in source_dir_list:
                loop_json = {}
                loop_json["slug"] = item
                loop_json["id"] = item
                loop_json["name"] = item
                if os.path.isfile(os.path.join(settings.SOURCE_FOLDER, item)):
                    path_type = "File"
                else:
                    path_type = "Folder"
                loop_json["description"] = f"{path_type} named {item}"
                return_slug.append(loop_json)
        return return_slug

def backup_folder_size():
    folder_bytes_size = 0
    for file in os.listdir(settings.BACKUP_FOLDER):
        filename = os.path.join(settings.BACKUP_FOLDER,file)
        if pyzipper.is_zipfile(filename):
            folder_bytes_size += os.path.getsize(filename)
    return folder_bytes_size

def generate_config():
    result = {}
    result["defaults"] = {
            "max_backups_in_ha": 4,
            "max_backups_in_google_drive": 4,
            "days_between_backups": 3,
            "delete_ignored_after_days": 0,
            "backup_name": "{type} Backup {year}-{month}-{day} {hr24}:{min}:{sec}",
            "low_space_threshold": 1073741824,
            "generational_days": 0,
            "generational_weeks": 0,
            "generational_months": 0,
            "generational_years": 0,
            "generational_day_of_week": "mon",
            "generational_day_of_month": 1,
            "generational_day_of_year": 1,
            "certfile": "/ssl/fullchain.pem",
            "keyfile": "/ssl/privkey.pem",
            "ingress_port": 8099,
            "port": 1627,
            "background_color": "#1c1c1c",
            "accent_color": "#03a9f4",
            "google_drive_timeout_seconds": 180,
            "google_drive_page_size": 100,
            "alternate_dns_servers": "8.8.8.8,8.8.4.4",
            "default_drive_client_id": "933944288016-n35gnn2juc76ub7u5326ls0iaq9dgjgu.apps.googleusercontent.com",
            "maximum_upload_chunk_bytes": 10485760,
            "folder_file_path": "/data/folder.dat",
            "credentials_file_path": "/data/credentials.dat",
            "retained_file_path": "/data/retained.json",
            "secrets_file_path": "/config/secrets.yaml",
            "backup_directory_path": "/backup",
            "ingress_token_file_path": "/data/ingress.dat",
            "config_file_path": "/data/options.json",
            "id_file_path": "/data/id.json",
            "data_cache_file_path": "/data/data_cache.json",
            "authorization_host": "https://habackup.io",
            "token_server_hosts": "https://token1.habackup.io,https://habackup.io",
            "drive_url": "https://www.googleapis.com",
            "drive_host_name": "www.googleapis.com",
            "drive_refresh_url": "https://www.googleapis.com/oauth2/v4/token",
            "drive_authorize_url": "https://accounts.google.com/o/oauth2/v2/auth",
            "drive_device_code_url": "https://oauth2.googleapis.com/device/code",
            "drive_token_url": "https://oauth2.googleapis.com/token",
            "save_drive_creds_path": "token",
            "stop_addon_state_path": "/data/stop_addon_state.json",
            "max_sync_interval_seconds": 3600,
            "backup_stale_seconds": 10800,
            "pending_backup_timeout_seconds": 18000,
            "failed_backup_timeout_seconds": 900,
            "new_backup_timeout_seconds": 5,
            "download_timeout_seconds": 60,
            "default_chunk_size": 5242880,
            "log_level": "DEBUG",
            "console_log_level": "INFO",
            "backup_startup_delay_minutes": 10,
            "exchanger_timeout_seconds": 10,
            "max_snapshots_in_hassio": 4,
            "max_snapshots_in_google_drive": 4,
            "days_between_snapshots": 3,
            "snapshot_name": "Snapshot {year}-{month}-{day} {hr24}:{min}:{sec}",
            }
    none_list = {
        "backup_time_of_day","backup_password","exclude_folders","extra_exclude_folders","exclude_addons","stop_addons",
        "drive_ipv4","default_drive_client_secret","drive_picker_api_key","supervisor_url",
        "hassio_header","server_project_id","snapshot_time_of_day","snapshot_password"}
    true_list = {"confirm_multiple_deletes","warn_for_low_space","enable_drive_upload"}
    false_list = {
            "ignore_upgrade_backups","delete_after_upload", "generational_delete_early",
            "ignore_other_backups","delete_before_new_backup","specify_backup_folder",
            "call_backup_snapshot","disable_watchdog_when_stopping","use_ssl","require_login",
            "expose_extra_server","verbose","send_error_reports","drive_experimental",
            "ignore_ipv6_addresses","ignore_other_snapshots","ignore_upgrade_snapshots",
            "specify_snapshot_folder","delete_before_new_snapshot"}
    old_list = {
        "notify_for_stale_snapshots","enable_snapshot_stale_sensor","enable_snapshot_state_sensor",
        "notify_for_stale_backups","enable_backup_stale_sensor","enable_backup_state_sensor",}
    for item in false_list | old_list:
        result["defaults"][item] = False
    for item in true_list:
        result["defaults"][item] = True
    for item in none_list:
        result["defaults"][item] = ""
    result["is_custom_creds"] = False
    if os.path.isfile(os.path.join(settings.SOURCE_FOLDER, item)):
        result["backup_folder"] = drive_requests.folder_id() # 1 sec for 10000 of 2 sec
        with open(settings.DATA_FOLDER+'options.json',encoding="utf-8") as options_file:
            options_data = json.load(options_file)
        for item in options_data:
            result["config"][item] = options_data[item]
    result["config"] = result["defaults"].copy()
    folders =  get_folder()
    list_memory = {"maximum_upload_chunk_bytes","google_drive_page_size",
                   "low_space_threshold","default_chunk_size"}
    for item in list_memory:
        result["config"][item] = converting.bytes_to_human(result["config"][item])
    list_time = {"max_sync_interval_seconds","delete_ignored_after_days",
        "google_drive_timeout_seconds","backup_stale_seconds","pending_backup_timeout_seconds",
        "failed_backup_timeout_seconds","new_backup_timeout_seconds","download_timeout_seconds",
        "backup_startup_delay_minutes","exchanger_timeout_seconds"}
    for item in list_time:
        result["config"][item] = converting.seconds_to_human(result["config"][item])
    result["folders"] = folders
    return result

def gen_backup_name_keys():
    now = datetime.datetime.now()
    isotime = now.strftime('%Y-%m-%dT%I:%M:%S.%f+00:00')
    # isotime = datetime.datetime.now().isoformat() + "+00:00"
    backup_name_keys =  {
    "{type}": "Full",
    "{year}": now.strftime('%Y'),
    "{year_short}": now.strftime('%y'),
    "{weekday}": now.strftime('%A'),
    "{weekday_short}": now.strftime('%a'),
    "{month}": now.strftime('%m'),
    "{month_long}": now.strftime('%B'),
    "{month_short}": now.strftime('%b'),
    "{ms}": now.strftime('%f'),
    "{day}": now.strftime('%d'),
    "{hr24}": now.strftime('%H'),
    "{hr12}": now.strftime('%I'),
    "{min}": now.strftime('%M'),
    "{sec}": now.strftime('%S'),
    "{ampm}": now.strftime('%p'),
    "{version_ha}": "2022.8.3",
    "{version_hassos}": "None",
    "{version_super}": "2022.08.3",
    "{date}": now.strftime('%m/%d/%y'), 
    "{time}": now.strftime('%H:%M:%S'),
    "{datetime}": now.strftime('%a %b %m %H:%M:%S %Y'),
    "{isotime}": isotime,
    "{hostname}": socket.gethostname()
    },
    return backup_name_keys[0]

def save_config(rx_data):
    data = generate_config()
    for item in data["defaults"]:
        try:
            rx_data["config"][item]
            if rx_data["config"][item] is None:
                raise Exception()
        except:
            rx_data["config"][item] = data["defaults"][item]
    list_memory = {"maximum_upload_chunk_bytes", "low_space_threshold", "default_chunk_size"}
    for item in list_memory:
        rx_data["config"][item] = int(converting.human_to_bytes(rx_data["config"][item]))
    list_time = {"max_sync_interval_seconds","delete_ignored_after_days",
    "google_drive_timeout_seconds", "google_drive_page_size", "backup_stale_seconds", "pending_backup_timeout_seconds",
    "failed_backup_timeout_seconds", "new_backup_timeout_seconds", "download_timeout_seconds", "backup_startup_delay_minutes",
    "exchanger_timeout_seconds"}
    for item in list_time:
        rx_data["config"][item] = int(converting.human_to_seconds(rx_data["config"][item]))    
    
    options_data = {}
    for item in rx_data['config']:
        if rx_data['config'][item] != data['defaults'][item]:
            options_data[item] = rx_data['config'][item]
    options_data["extra_exclude_folders"] = data["config"]["extra_exclude_folders"]
    with open(settings.DATA_FOLDER + 'options.json', 'w', encoding="utf-8") as f:
        json.dump(options_data, f, indent=2)

def get_backup_folder_size():
    size = 0
    for path, dirs, files in os.walk(settings.BACKUP_FOLDER):
        for f in files:
            fp = os.path.join(path, f)
            size += os.path.getsize(fp)
    return size