"""
Used for creating,deleting and changing infos of backups.
"""
import sys
import json
import os
import random
import time
import threading
import string
import multiprocessing
from datetime import datetime, timedelta
from io import BytesIO
import logger
import pyzipper
import settings
import google_api
import drive_requests

def is_encrypted(filename):
    """
    Tries to open the zip file if it fails it is encrypte.
    """
    with pyzipper.AESZipFile(filename) as zip_file:
        try:
            zip_file.testzip()
            return False
        except RuntimeError:
            return True

def gen_info(backup_name,protected):
    """
    Generates information about a backup file.
    It includes:
    slug, name, timestamps, protected and included/excluded folders.
    """
    json_data = {
            "slug": ''.join(
                        random.SystemRandom().choice(string.ascii_lowercase + string.digits)
                        for _ in range(8)),
            "ignored": False,
            "name": backup_name,
            "timestamp": time.time(),
            "creation_time": datetime.now().strftime('%a %b %m %H:%M:%S %Y'),
            "folders": [filename for filename in os.listdir(settings.SOURCE_FOLDER)],
            "addons": [],
            "protected": protected,
            "exclude_folders": google_api.generate_config()["config"]["exclude_folders"],
        }
    return_data=json.dumps(json_data, indent=4, sort_keys=True)
    return return_data

def gen_name(full_backup=True):
    """
    Generates a name for a backup file based on the settings.

    If `full_backup`, the name will be based on the `backup_name` setting else `snapshot_name`.
    The backup name will be templated from the settings.
    """
    config = google_api.generate_config()["config"]
    backup_name = config["backup_name"] if full_backup else config["snapshot_name"]
    backup_keys = google_api.gen_backup_name_keys()
    for key, value in backup_keys.items():
        backup_name = backup_name.replace(key, value)
    return backup_name

def set_retention(slug, expect_retained_ha):
    """
    Sets the retention status of a file with the given file ID slug in the backup folder.

    The function ensures that the file is(not) marked as retained.
    And repacks the zip if needed.
    """
    filename= get_filename(get_name(slug))
    if not os.path.isfile(filename):
        return False
    zip_delete_ha = False
    with pyzipper.ZipFile(filename) as zip_file:
        is_retained_ha = "retained" in zip_file.namelist()
        if expect_retained_ha != is_retained_ha:
            if is_retained_ha:
                zip_delete_ha = True
            else:
                zip_comp = settings.ZIP_COMPRESSION
                with pyzipper.AESZipFile(filename,'a',compression=zip_comp) as zip_file:
                    zip_file.writestr("retained", "")
                    return True
    if zip_delete_ha:
        memory_file = BytesIO()
        with pyzipper.AESZipFile(memory_file,'w',compression=pyzipper.ZIP_DEFLATED) as zip_out, \
                pyzipper.AESZipFile(filename) as zip_file:
            exclude = "info.jsonnote.txtretained"
            zip_out.writestr("info.json",zip_file.read("info.json"))
            if "note.txt" in zip_file.namelist():
                zip_out.writestr("note.txt",zip_file.read("note.txt"))
            protected = json.loads(zip_file.read("info.json"))["protected"]
            if protected:
                password = google_api.generate_config()["config"]["backup_password"]
                zip_file.setencryption(pyzipper.WZ_AES, nbits=256)
                zip_file.pwd=password.encode()
                zip_out.setencryption(pyzipper.WZ_AES, nbits=256)
                zip_out.pwd=password.encode()
            for item in zip_file.infolist():
                buffer = zip_file.read(item.filename)
                if item.filename not in exclude:
                    zip_out.writestr(item, buffer)
        with open(filename, "wb") as zip_out:
            zip_out.write(memory_file.getvalue())
    return True

def is_backup(filename):
    """
    Determines if a file is a backup file.
    """
    if if os.path.isdir(filename):
        return False
    try:
        with pyzipper.AESZipFile(filename) as zip_file:
            return "info.json" in zip_file.namelist()
    except pyzipper.BadZipFile:
        return False

def request(backup_name="",note="",retained_local=False,retain_drive=False):
    """
    Request a backup in the background.
    """
    settings.backup_running = True
    backup_name = valid_backup_name(backup_name)
    threading.Thread(
            target=_create,daemon = True,
            args=(backup_name,note,retained_local,retain_drive,),
            name="Background Backup",).start()
    return backup_name

def valid_backup_name(backup_name):
    """
    Test if backup name is valid and exists.
    """
    backup_config = google_api.generate_config()["config"]
    if backup_name == "" or len(backup_name) < 1:
        backup_name = gen_name(backup_config["exclude_folders"] == "")
    backup_name = backup_name.replace(":",".")
    i = 0
    origin_backup_name = backup_name
    while True:
        if not os.path.exists(os.path.join(settings.BACKUP_FOLDER,backup_name + ".zip")):
            break
        i += 1
        backup_name = f"{origin_backup_name} ({i})"
    return backup_name

def _create(backup_name,note,retained_local,retained_drive):
    """
    Generates a backup name based on the type.
    All infos are written it in the info.txt file in the backup together with all data.
    """
    settings.backup_running = True
    backup_config = google_api.generate_config()["config"]
    backup_zip_name = os.path.join(settings.BACKUP_FOLDER, backup_name + ".zip")
    password=backup_config["backup_password"]
    protected = password != ""
    backup_info = gen_info(backup_name,protected)
    json_backup_info = json.loads(backup_info)
    settings.running_backup_info = {
      "slug": json_backup_info["slug"],
      "name": json_backup_info["name"],
      "protected": json_backup_info["protected"],
      "timestamp": json_backup_info["timestamp"],
      "date": json_backup_info["creation_time"],
      "type": "full" if json_backup_info["exclude_folders"] == "" else "partial",
      "status": "HA Only",
      "isPending": True,
      "sources": [
        {
          "key": "HomeAssistant",
          "name": json_backup_info["name"],
          "slug": json_backup_info["slug"]
        }
      ],
      "createdAt": "just now"
    }
    try:
        zip_comp = settings.ZIP_COMPRESSION
        with pyzipper.AESZipFile(backup_zip_name,'w',compression=zip_comp) as zip_file:
            zip_file.writestr("info.json", backup_info)
            if note:
                zip_file.writestr("note.txt", note)
            if retained_local:
                zip_file.writestr("retained", "")
            if protected or True:
                zip_file.setencryption(pyzipper.WZ_AES, nbits=256)
                zip_file.pwd=password.encode()
            for root, folders, files in os.walk(settings.SOURCE_FOLDER):
                for folder_name in folders:
                    absolute_path = os.path.join(root, folder_name)
                    rel_path = absolute_path.replace(settings.SOURCE_FOLDER,"")
                    if is_included(backup_name,backup_config,absolute_path,rel_path):
                        zip_path=absolute_path.replace(settings.SOURCE_FOLDER,"./backup/")
                        zip_file.write(absolute_path,zip_path)
                for file_name in files:
                    absolute_path = os.path.join(root, file_name)
                    rel_path = absolute_path.replace(settings.SOURCE_FOLDER,"")
                    if is_included(backup_name,backup_config,absolute_path,rel_path):
                        zip_path=absolute_path.replace(settings.SOURCE_FOLDER,"./backup/")
                        zip_file.write(absolute_path,zip_path)
            logger.debug(f"'{backup_name}' created successfully.")
    except IOError as message:
        logger.error(message)
        sys.exit(1)
    except pyzipper.BadZipfile as message:
        logger.error(message)
        sys.exit(1)
    except RuntimeError as message:
        logger.error(message)
        sys.exit(1)
    except UnicodeEncodeError as message:
        pass
    finally:
        settings.backup_running = False
        settings.running_backup_info = {}
    threading.Thread(target=drive_requests.upload_file, args=(backup_name,retained_drive,)).start()
    return backup_name

def is_included(backup_name, backup_config, absolute_path, name):
    """
    Check if a file or folder should be included from the backup.
    """
    if backup_name in name or name == backup_name:
        return False
    if not backup_config["exclude_folders"] and not backup_config["extra_exclude_folders"]:
        print("wdwad")
        return True
    all_exclude_folders = []
    if backup_config["extra_exclude_folders"]:
        all_exclude_folders += backup_config["extra_exclude_folders"].split(",")
    if backup_config["extra_exclude_folders"]:
        all_exclude_folders += backup_config["exclude_folders"].split(",")
    if any(name.startswith(folder) for folder in list(filter(None, all_exclude_folders))):
        return False
    if is_backup(absolute_path):
        return False
    return True

def get_name(slug):
    """
    Returns the name of the file with the specified slug from the BACKUP_FOLDER.
    If the file is not found, returns False.
    """
    for filename in os.listdir(settings.BACKUP_FOLDER):
        file = os.path.join(settings.BACKUP_FOLDER, filename)
        if not pyzipper.is_zipfile(file):
            continue
        with pyzipper.ZipFile(file,'r') as read_zip_file:
            info_json = json.loads(read_zip_file.read("info.json"))
            if info_json["slug"] == slug:
                return info_json["name"]
    return False

def delete(slug):
    """
    Delete a local backup of a given slug.
    """
    file_name = get_name(slug)
    filename = get_filename(file_name+".zip")
    if "retained" in pyzipper.AESZipFile(filename).namelist():
        return False, "Backup is retained"
    try:
        os.remove(filename)
        return True, ""
    except FileNotFoundError:
        return False, "File not found."

def get_filename(name):
    """
    Returns the file path of the file with the specified name in the BACKUP_FOLDER.
    If the file is not found, returns False.
    """
    filename = os.path.join(settings.BACKUP_FOLDER, name)
    if os.path.isfile(filename+".zip"):
        return filename+".zip"
    if os.path.isfile(filename):
        return filename
    return False

def retained_ha(name):
    """
    Returns whether the backup with the specified name in the BACKUP_FOLDER is retained.
    """
    try:
        with pyzipper.ZipFile(get_filename(name)) as zip_file:
            return "retained" in zip_file.namelist()
    except pyzipper.BadZipFile:
        return False

def number_ha_retained():
    """
    Count the number of retained files in the BACKUP_FOLDER.
    """
    with multiprocessing.Pool(processes=8) as pool:
        results = pool.map(retained_ha, os.listdir(settings.BACKUP_FOLDER))
    numbers = sum(results)
    settings.bootstrap_functions_data["number_ha_retained"] = numbers
    return numbers

def set_note(slug, note):
    """
    Write the new backup note to the local backup.
    """
    name = get_name(slug)
    if not name:
        return False
    filename= get_filename(name)
    with pyzipper.AESZipFile(filename) as zip_file:
        if "note.txt" not in zip_file.namelist():
            with pyzipper.AESZipFile(filename,"a") as zip_file:
                zip_file.writestr("note.txt",note)
                return True
        else:
            memory_file = BytesIO()
            with pyzipper.AESZipFile(memory_file,'w', compression=pyzipper.ZIP_DEFLATED) as zip_out:
                exclude = "info.jsonnote.txt"
                zip_out.writestr("info.json",zip_file.read("info.json"))
                zip_out.writestr("note.txt",note)
                protected = json.loads(zip_file.read("info.json"))["protected"]
                if protected:
                    password = google_api.generate_config()["config"]["backup_password"]
                    zip_file.setencryption(pyzipper.WZ_AES, nbits=256)
                    zip_file.pwd=password.encode()
                    zip_out.setencryption(pyzipper.WZ_AES, nbits=256)
                    zip_out.pwd=password.encode()
                for item in zip_file.infolist():
                    buffer = zip_file.read(item.filename)
                    if item.filename not in exclude:
                        zip_out.writestr(item, buffer)
            with open(filename, "wb") as new_backup:
                new_backup.write(memory_file.getvalue())
    return False

def backup_timestamp_drive(file):
    """
    This function is used by last_backup_drive function in a multithreaded pool.
    """
    return float(file["appProperties"]["TIMESTAMP"])

def last_backup_drive():
    """
    This function gets the last created backup from Google Drive.
    """
    with multiprocessing.Pool(processes=8) as pool:
        results_drive = pool.map(backup_timestamp_drive, settings.drive_data_cache )
    results_drive.append(0)
    last_backup = max(filter(None.__ne__, results_drive))
    settings.bootstrap_functions_data["last_backup_drive"] = last_backup
    return last_backup

def backup_timestamp(filename):
    """
    Tries to open a backup and checks if the info file exists.
    """
    try:
        if not pyzipper.is_zipfile(filename):
            return
        filename = os.path.join(settings.BACKUP_FOLDER,filename)
        with pyzipper.ZipFile(filename) as read_zip_file:
            return json.loads(read_zip_file.read("info.json"))["timestamp"]
    except pyzipper.BadZipfile:
        pass

def last_backup_ha():
    """
    Gets the timestamp of the last backup stored locally.
    """
    desired_file_list = [os.path.join(settings.BACKUP_FOLDER,file_name)
                         for file_name in os.listdir(settings.BACKUP_FOLDER)]
    with multiprocessing.Pool(processes=8) as pool:
        results = pool.map(backup_timestamp, desired_file_list)
    results.append(0)
    last_backup = max(filter(None.__ne__, results))
    settings.bootstrap_functions_data["last_backup_ha"] = last_backup
    return last_backup

def last():
    """
    Gets the timestamp of the last backup stored locally or Google Drive.
    """
    drive_timespamp = threading.Thread(target=last_backup_drive)
    drive_timespamp.start()
    last_timestamp_ha = last_backup_ha()
    drive_timespamp.join()
    last_timestamp_drive = settings.bootstrap_functions_data["last_backup_drive"]
    last_backup = max(last_timestamp_drive, last_timestamp_ha)
    settings.bootstrap_functions_data["last_backup"] = last_backup
    return last_backup

def next_backup(last_backup=0):
    """
    Calculates the next backup timestamp from the last backup and the settings.
    """
    last_backup = datetime.fromtimestamp(last_backup or last())
    config = google_api.generate_config()["config"]
    backup_time = last_backup + timedelta(days=int(config["days_between_backups"]))
    if config["backup_time_of_day"]:
        backup_time_hour,backup_time_minute = map(int,config["backup_time_of_day"].split(":"))
        backup_time = backup_time.replace(hour=backup_time_hour,minute=backup_time_minute)
    return backup_time.timestamp()
