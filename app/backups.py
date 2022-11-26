import sys
import json
import os
import random
import time
import threading
import string
import multiprocessing
import datetime
from io import BytesIO
import logger
import pyzipper
import settings
import google_api
import drive_requests

def is_encrypted(filename):
    with pyzipper.AESZipFile(filename) as zip_file:
        try:
            zip_file.testzip()
            return False
        except:
            return True

def gen_info(backup_name,protected):
    json_data = {"slug": ''.join(random.SystemRandom().choice(string.ascii_lowercase + string.digits) for _ in range(8)) }
    json_data["ignored"] = False
    json_data["name"] = backup_name
    json_data["timestamp"] = time.time()
    json_data["creation_time"] = datetime.datetime.now().strftime('%a %b %m %H:%M:%S %Y')
    json_data["folders"] = [filename for filename in os.listdir(settings.SOURCE_FOLDER)]
    json_data["addons"] = []
    json_data["protected"] = protected
    json_data["exclude_folders"] = google_api.generate_config()["config"]["exclude_folders"]
    return_data=json.dumps(json_data, indent=4, sort_keys=True)
    return return_data

def gen_name(full_backup=True):
    config = google_api.generate_config()["config"]
    backup_name = config["backup_name"]
    if not full_backup:
        backup_name = config["snapshot_name"]
    backup_name_keys = google_api.gen_backup_name_keys()
    for key in backup_name_keys:
        backup_name = backup_name.replace(key, backup_name_keys[key])
    return backup_name

def set_retention(slug, expect_retained_ha):
    zip_delete_ha = False
    filename= get_filename(get_name(slug))
    if os.path.isfile(filename):
        with pyzipper.ZipFile(filename) as zip_file:
            is_retained_ha = "retain_ha" in zip_file.namelist()
            if expect_retained_ha != is_retained_ha:
                if is_retained_ha:
                    zip_delete_ha = True
                else:
                    with pyzipper.AESZipFile(filename,'a',compression=eval(settings.ZIP_COMPRESSION)) as zip_file:
                        zip_file.writestr("retain_ha", "")
                        return True
    if zip_delete_ha:
        memory_file = BytesIO()
        with pyzipper.AESZipFile(memory_file, 'w', compression=pyzipper.ZIP_DEFLATED) as zip_out, pyzipper.AESZipFile(filename) as zip_file:
            exclude = "info.jsonnote.txtretain_ha"
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
                if (item.filename not in exclude):
                    zip_out.writestr(item, buffer)
        with open(filename, "wb") as f:
            f.write(memory_file.getvalue())
    return True

def is_backup(filename):
    try:
        with pyzipper.AESZipFile(filename) as zip_file:
            return "info.json" in zip_file.namelist()
    except:
        return False

def request(backup_name="",note="",retain_ha=False,retain_drive=False):
    settings.backup_running = True
    backup_name = valid_backup_name(backup_name)
    threading.Thread(target=_create,args=(backup_name,note,retain_ha,retain_drive,), name="Background Backup", daemon = True ).start()
    return backup_name

def valid_backup_name(backup_name):
    backup_config = google_api.generate_config()["config"]
    if backup_name == "" or len(backup_name) < 1:
        backup_name = gen_name(backup_config["exclude_folders"] == "")
    backup_name = backup_name.replace(":",".")
    i = 0
    while True:
        if not os.path.exists(os.path.join(settings.BACKUP_FOLDER,backup_name + ".zip")):
            break
        i += 1
        backup_name = f"{backup_name} ({i})"
    return backup_name

def _create(backup_name,note,retain_ha,retain_drive):
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
        with pyzipper.AESZipFile(backup_zip_name,'w',compression=eval(settings.ZIP_COMPRESSION)) as zip_file:
            zip_file.writestr("info.json", backup_info)
            if note:
                zip_file.writestr("note.txt", note)
            if retain_ha:
                zip_file.writestr("retain_ha", "")
            if retain_drive:
                zip_file.writestr("retain_drive", "")
            if protected:
                zip_file.setencryption(pyzipper.WZ_AES, nbits=256)
                zip_file.pwd=password.encode()
            for root, folders, files in os.walk(settings.SOURCE_FOLDER):
                for folder_name in folders:
                    absolute_path = os.path.join(root, folder_name)
                    if is_excluded(backup_name, backup_config, absolute_path, absolute_path.replace(settings.SOURCE_FOLDER,"")):
                        zip_file.write(absolute_path, absolute_path.replace(settings.SOURCE_FOLDER,"./backup/"))
                for file_name in files:
                    absolute_path = os.path.join(root, file_name)
                    if is_excluded(backup_name, backup_config, absolute_path, absolute_path.replace(settings.SOURCE_FOLDER,"")):
                        zip_file.write(absolute_path, absolute_path.replace(settings.SOURCE_FOLDER,"./backup/"))
            logger.debug("'%s' created successfully." % backup_name)
    except IOError as message:
        logger.error(message)
        sys.exit(1)
    except OSError as message:
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
        zip_file.close()
        settings.backup_running = False
        settings.running_backup_info = {}
    threading.Thread(target=drive_requests.upload_file, args=(backup_name,)).start()
    return backup_name

def is_excluded(backup_name, backup_config, absolute_path, name):
    if backup_name in name:
        return False
    if name == backup_name:
        return False
    if len(backup_config["exclude_folders"]) == 0 and len(backup_config["extra_exclude_folders"]) == 0:
        return True
    if len(backup_config["extra_exclude_folders"]) == 0 and (list(filter(name.startswith, backup_config["exclude_folders"].split(","))) != []):
        return False
    if len(backup_config["exclude_folders"]) == 0 and (list(filter(name.startswith, backup_config["extra_exclude_folders"].split(","))) != []):
        return False
    if is_backup(absolute_path):
        return False
    return True

def get_name(slug):
    for filename in os.listdir(settings.BACKUP_FOLDER):
        file = os.path.join(settings.BACKUP_FOLDER, filename)
        if not pyzipper.is_zipfile(file):
            continue
        with pyzipper.ZipFile(file, 'r', compression=pyzipper.ZIP_DEFLATED) as read_zip_file:
            info_json = json.loads(read_zip_file.read("info.json"))
            if info_json["slug"] == slug:
                return info_json["name"]
    return False

def delete(slug):
    file_name = get_name(slug)
    filename = get_filename(file_name+".zip")
    if "retain_ha" in pyzipper.AESZipFile(filename).namelist():
        return False, "Backup is retained"
    try:
        os.remove(filename)
        return True, ""
    except Exception as message:
        logger.error(message)
        return False, message

def get_filename(name):
    filename = os.path.join(settings.BACKUP_FOLDER, name+".zip")
    if os.path.isfile(filename):
        return filename
    filename = os.path.join(settings.BACKUP_FOLDER, name)
    if os.path.isfile(filename):
        return filename
    return False

def retained_ha(name):
    retained = False
    try:
        with pyzipper.ZipFile(get_filename(name)) as zip_file:
            retained = "retain_ha" in zip_file.namelist()
    finally:
        return retained

def number_ha_retained():
    desired_file_list = [file_name for file_name in os.listdir(settings.BACKUP_FOLDER)]
    with multiprocessing.Pool(processes=8) as pool:
        results = pool.map(retained_ha, desired_file_list)
    results = [x for x in results if x != None]
    numbers = results.count(True)
    settings.bootstrap_functions_data["number_ha_retained"] = numbers
    return numbers

def set_note(slug, note):
    name = get_name(slug)
    if name:
        filename= get_filename(name)
        with pyzipper.AESZipFile(filename) as zip_file:
            if "note.txt" not in zip_file.namelist():
                with pyzipper.AESZipFile(filename,"a") as zip_file:
                    zip_file.writestr("note.txt",note)
                    return True  
            else:
                mf = BytesIO()
                with pyzipper.AESZipFile(mf, 'w', compression=pyzipper.ZIP_DEFLATED) as zip_out:
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
        with open(filename, "wb") as f:
            f.write(mf.getvalue())
    return False

def backup_timestamp_drive(file):
    return float(file["appProperties"]["TIMESTAMP"])

def last_backup_drive(last_timestamp_drive={}):
    with multiprocessing.Pool(processes=8) as pool:
        results_drive = pool.map(backup_timestamp_drive, settings.drive_data_cache )
    # https://stackoverflow.com/questions/2577233/threading-in-python-retrieve-return-value-when-using-target
    results_drive.append(0)
    last_timestamp_drive[0] = max(filter(None.__ne__, results_drive))
    settings.bootstrap_functions_data["last_backup_drive"] = last_timestamp_drive[0]
    return last_timestamp_drive[0]


def backup_timestamp(filename):
    try:
        filename
        if not pyzipper.is_zipfile(filename):
            return
        filename = os.path.join(settings.BACKUP_FOLDER,filename)
        with pyzipper.ZipFile(filename) as read_zip_file:
            return json.loads(read_zip_file.read("info.json"))["timestamp"]
    except pyzipper.BadZipfile:
        pass

def last_backup_ha(last_timestamp_ha={}):
    desired_file_list = [ os.path.join(settings.BACKUP_FOLDER,file_name) for file_name in os.listdir(settings.BACKUP_FOLDER) ]
    with multiprocessing.Pool(processes=8) as pool:
        results = pool.map(backup_timestamp, desired_file_list)
    results.append(0)
    last_timestamp_ha[0] = max(filter(None.__ne__, results))  
    settings.bootstrap_functions_data["last_backup_ha"] = last_timestamp_ha[0]
    return last_timestamp_ha[0]

def last():
    last_timestamp_ha = {}
    last_timestamp_drive = {}
    drive_timespamp = threading.Thread(target=last_backup_drive,args=(last_timestamp_drive,))
    drive_timespamp.start()
    last_backup_ha(last_timestamp_ha)
    drive_timespamp.join()
    last_timestamp_ha = last_timestamp_ha[0]
    last_timestamp_drive = last_timestamp_drive[0]
    last_backup = last_timestamp_drive if last_timestamp_drive > last_timestamp_ha else last_timestamp_ha
    settings.bootstrap_functions_data["last_backup"] = last_backup
    return last_backup

def next(last_backup=0):
    if last_backup == 0:
        last_backup = datetime.datetime.fromtimestamp(last())
    else:
        last_backup = datetime.datetime.fromtimestamp(last_backup)
    config = google_api.generate_config()["config"]
    days = last_backup.day + config["days_between_backups"]
    backup_time_of_day = config["backup_time_of_day"]
    months = last_backup.month
    years = last_backup.year
    if backup_time_of_day == "":
        hours = last_backup.hour
        minutes = last_backup.minute
    else:
        hours = int(backup_time_of_day.split(":")[0])
        minutes = int(backup_time_of_day.split(":")[1])
    if months == datetime.datetime.now().month and days == datetime.datetime.now().day and years == datetime.datetime.now().year:
        if hours < datetime.datetime.now().hour and minutes < datetime.datetime.now().minute:
            days += 1
    while True:
        try:
            end_time_2 = datetime.datetime(years, months, days, hours, minutes, last_backup.second)
        except:
            if months == 12:
                years -= 1
                months = 1
            days -= (datetime.date(years, months+1, 1) - datetime.date(years, months, 1)).days
            months += 1
        else:
            return end_time_2.timestamp()
