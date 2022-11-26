import requests
import json
import datetime
import time
import os
import urllib
import base64
import math
import logger
import pyzipper
import get_status
import settings
import converting

def valid_access_token():
    path = settings.DATA_FOLDER + "credentials.dat"
    if not os.path.isfile(path):
        return False
    credentials_file = open(path, 'r', encoding="utf-8")
    data = json.load(credentials_file)
    token_expiry = data['token_expiry']
    datemask1 = "%Y-%m-%dT%H:%M:%SZ"
    datemask2 = "%Y-%m-%d %H:%M:%S"
    datetime_object = datetime.datetime.utcnow()
    currdate = datetime.datetime.strftime(datetime_object,datemask2)
    time_2 = datetime.datetime.strptime(token_expiry, datemask1)
    time_1 = datetime.datetime.strptime(currdate, datemask2)
    time_interval = time_2 - time_1
    if "-" not in str(time_interval) and str(time_interval) >= "00:05:00":
        return  True
    return False

def access_token():
    path = settings.DATA_FOLDER + "credentials.dat"
    f = open(path, 'r', encoding="utf-8")
    data = json.load(f)
    if valid_access_token():
        google_access_token = data['access_token']
        return str(google_access_token)
    else:
        refresh_token = data['refresh_token']
        answer = requests.post(
        'https://habackup.io/drive/refresh',
        json={"refresh_token": refresh_token},
        timeout=10
        )
        unicode_text = answer.content.decode('utf-8')
        data = json.loads(unicode_text)
        access_token = data['access_token']
        path = settings.DATA_FOLDER + "credentials.dat"
        with open(path, 'w', encoding="utf-8") as f:
            json.dump(data, f)
        return str(access_token)

def folder_id():
    if not os.path.exists(os.path.join(settings.DATA_FOLDER ,"credentials.dat")):
        return ""
    folder_id_file = os.path.join(settings.DATA_FOLDER, "folder.dat")
    try:
        folderid = open(folder_id_file, encoding="utf-8").read()
        if len(folderid) == 33:
            return folderid
    except:
        if drive_folder_exists():
            q = 'name="'+settings.DRIVE_FOLDER_NAME+'" and mimeType="application/vnd.google-apps.folder" and trashed=false'
            files = requests.get(
                "https://www.googleapis.com/drive/v3/files?&q=" + urllib.parse.quote(q),
                headers={"Authorization": "Bearer " + access_token()}, timeout=10
            )
            data = json.loads(files.text)
            id = data['files'][0]['id']
        else:
            id = create_drive_folder()
        with open(folder_id_file, 'w') as folderid:
            folderid.write(id)
        return str(id)

def get_filename(name):
    filename = os.path.join(settings.BACKUP_FOLDER, name+".zip")
    if os.path.isfile(filename):
        return filename
    return os.path.join(settings.BACKUP_FOLDER, name)

def create_drive_folder():
    headers = {
        'Authorization': 'Bearer ' + access_token(),
        'Content-Type': 'application/json; charset=UTF-8'
    }
    querystring = '{"name":"'+settings.DRIVE_FOLDER_NAME+'","mimeType":"application/vnd.google-apps.folder"}'
    files = requests.post(
        'https://www.googleapis.com/drive/v3/files',
        headers=headers,
        data=querystring,
        timeout=10
    )
    data = json.loads(files.text)
    id = data['id']
    return id

def drive_folder_exists():
    q = 'name="'+settings.DRIVE_FOLDER_NAME+'" and mimeType="application/vnd.google-apps.folder" and trashed=false'
    files = requests.get(
        "https://www.googleapis.com/drive/v3/files?&q=" + urllib.parse.quote(q),
        headers={"Authorization": "Bearer " + access_token()},
        timeout=10
    )
    data = json.loads(files.text)
    try:
        file_id = data['files'][0]['id']
        return True
    except:
        return False

def get_file_size():
    response = requests.get("https://www.googleapis.com/drive/v2/about",
                            headers={"Authorization": "Bearer "+access_token()},
                            timeout=10
                            )
    data = response.json()
    bytes_total = data['quotaBytesTotal']
    bytes_used = data['quotaBytesUsed']
    free_space = int(bytes_total) - int(bytes_used)
    return free_space , bytes_used

def upload_session_url(filename):
    file_name = get_filename(filename)
    file_size = str(os.path.getsize(file_name))
    headers = {
        'Authorization': 'Bearer ' + access_token(),
        'Content-Type': 'application/json; charset=UTF-8',
        'X-Upload-Content-Type': 'application/x-zip-compressed',
        'X-Upload-Content-Length': file_size,
        'X-Upload-Content-Range': 'bytes 0-{}/{}'.format(file_size, file_size)
    }
    querystring = {"uploadType": "resumable"}
    logo = open("logo/drive_logo.png","rb")
    urlsafe = base64.urlsafe_b64encode(logo.read()).decode('utf8')
    drive_content_hints = '"contentHints": {"thumbnail": { "image": "'+urlsafe+'", "mimeType": "image/png" } } '
    drive_parents_folder = '"parents": ["'+ folder_id() +'"]'
    drive_description = '"description": "This is a backup file"'
    if not os.path.isfile(os.path.join(settings.BACKUP_FOLDER,filename)):
        filename += ".zip"
    drive_file_name = '"name": "'+filename+'"'
    with pyzipper.AESZipFile(file_name) as zip_file:
        backup_json_data = json.loads(zip_file.read("info.json"))
        note = zip_file.read("note.txt").decode() if "note.txt" in zip_file.namelist() else None
        retained_drive = "retain_drive" in zip_file.namelist()        
        info_json = json.loads(zip_file.read("info.json"))
        folders = get_status.zip_file_folders(zip_file)    
    currdate = datetime.datetime.strftime(datetime.datetime.today(),"%Y-%m-%dT%H:%M :%SZ")
    drive_creation_time = '"createdTime": "'+datetime.datetime.fromtimestamp(backup_json_data["timestamp"]).strftime("%Y-%m-%dT%H:%M:%SZ")+'"'
    drive_modificition_time = '"createdTime": "'+datetime.datetime.fromtimestamp(backup_json_data["timestamp"]).strftime("%Y-%m-%dT%H:%M:%SZ")+'"'
    properties = {
        "SLUG": backup_json_data["slug"],
        "NAME": backup_json_data["name"],
        "PROTECTED": str(backup_json_data["protected"]),
        "TYPE": "full" if backup_json_data["exclude_folders"] == "" else "partial",
        "TIMESTAMP" : backup_json_data['timestamp'],
        "RETAINED": str(retained_drive),
        "NOTE": "" if note is None else str(note),
        
    }
    folder_i = 1
    for folder in folders:
        properties[f"FOLDER_{folder_i}"] = json.dumps(folder)
        folder_i += 1
    appProperties = '"appProperties": ' + str(properties) + ''
    payload = '{'+appProperties+','+drive_content_hints+','+drive_file_name+','+drive_description+','+drive_creation_time+','+drive_modificition_time+','+drive_parents_folder+'}'    
    response = requests.post(
        'https://www.googleapis.com/upload/drive/v3/files',
        headers=headers,
        data=payload,
        params=querystring,
        timeout=10
    )
    if response.status_code == 200:
        sessionUri = response.headers['Location']
        return sessionUri
    else:
        return

def set_note(file_id_slug,new_note):
    if len(file_id_slug) == 8:
        file_id_slug = get_file_id(file_id_slug)
    url = f"https://www.googleapis.com/drive/v3/files/{file_id_slug}/?fields=appProperties&supportsAllDrives=true" #&access_token" + access_token()
    headers = { 'Authorization': 'Bearer ' + access_token() }
    new_note = "" if new_note is None else str(new_note)
    json = {'appProperties': {'NOTE': new_note}, 'description': new_note}
    try:
        response = requests.request("PATCH", url, headers=headers, json=json)
        if response.status_code < 400:
            settings.refresh_drive_data = True
            return True
    except:
        settings.refresh_drive_data = True
    return False

def set_retention(file_id_slug, retention):
    retention = str(retention)
    if len(file_id_slug) == 8:
        file_id_slug = get_file_id(file_id_slug)
    if not file_id_slug:
        return False
    try:
        url = f"https://www.googleapis.com/drive/v3/files/{file_id_slug}/?fields=appProperties&supportsAllDrives=true"
        headers = { 'Authorization': 'Bearer ' + access_token() }
        json = {'appProperties': {'RETAINED': retention}, 'description': retention}
        response = requests.request("PATCH", url, headers=headers, json=json)
        if response.status_code == 200:
            settings.refresh_drive_data = True
            return True
    except:
        pass
    settings.refresh_drive_data = True
    return False

def upload_file(filename):
    settings.uploading_data_cache[filename] = {}
    settings.uploading_data_cache[filename]["name"] = "Google Drive"
    settings.uploading_data_cache[filename]["started"] = time.time()
    settings.uploading_data_cache[filename]["speed"] = 0
    settings.uploading_data_cache[filename]["progress"] = 0
    file_name = get_filename(filename)
    file_size = os.path.getsize(file_name)
    sessionUri = upload_session_url(filename)
    in_file = open(file_name, "rb")
    try:
        if file_size <= 5242880:
            data2 = in_file.read()
            headers = {
                'Content-Length': str(file_size),
                'Content-Type': "application/x-zip-compressed"
            }
            response = requests.request(
                "PUT", sessionUri, data=data2, headers=headers, timeout=10)
            settings.uploading_data_cache.pop(filename)
            settings.refresh_drive_data = True
            in_file.close()
            return response.content
        else:
            # https://stackoverflow.com/questions/39887303/resumable-upload-in-drive-rest-api-v3
            upload_start = time.time()
            in_file = open(file_name, "rb")
            chunk = in_file.read()
            BASE_CHUNK_SIZE = 256 * 1024 # 262144
            CHUNK_SIZE = 8 * BASE_CHUNK_SIZE
            CHUNK_SIZE = 4 * BASE_CHUNK_SIZE
            TOTAL_BYTES = file_size
            first_byte = 0
            last_byte = CHUNK_SIZE - 1
            times = int(math.ceil(file_size/CHUNK_SIZE))
            for _ in range(times):
                if last_byte > TOTAL_BYTES:
                    last_byte = TOTAL_BYTES -1
                settings.uploading_data_cache[filename]["progress"] = (first_byte/file_size)*100
                settings.uploading_data_cache[filename]["speed"] = first_byte/(time.time() - settings.uploading_data_cache[filename]["started"])
                data2 = chunk[first_byte:last_byte+1]
                headers = {
                    'Content-Length': str(TOTAL_BYTES),
                    'Content-Type': "application/x-zip-compressed",
                    'Content-Range': "bytes " + str(first_byte) +"-"+str(last_byte)+"/"+str(TOTAL_BYTES)
                }
                response = requests.request(
                    "PUT", sessionUri, data=data2, headers=headers, timeout=10)
                if response.status_code == 200 and times-1 == _:
                    logger.debug(f"Uploaded backup { file_name } to Google Drive in {time.time()-upload_start} seconds")
                    settings.uploading_data_cache.pop(filename)
                    settings.refresh_drive_data = True
                    in_file.close()
                    return True
                byte_range = response.headers["Range"]
                first_byte = byte_range.split("=",1)[1].split("-",1)[0]
                last_byte = byte_range.split("=",1)[1].split("-",1)[1]
                # percentage = str((int(last_byte)/file_size)*100)[:2]+"%"
                first_byte = int(last_byte)+1
                last_byte = int(first_byte)+CHUNK_SIZE
    except:
        settings.refresh_drive_data = True
        settings.uploading_data_cache.pop(filename)

def download(slug_name):
    name = name_from_slug(slug_name)
    if not name:
        name = slug_name
    settings.uploading_data_cache[name] = {}
    settings.uploading_data_cache[name]["name"] = "Home Assistant"
    settings.uploading_data_cache[name]["started"] = time.time()
    settings.uploading_data_cache[name]["speed"] = 0
    settings.uploading_data_cache[name]["progress"] = 0    
    file_name =  os.path.join(settings.BACKUP_FOLDER, name)
    file_id = get_file_id(slug_name)
    if not file_id:
        logger.error("File not found in Google Drive")
        return False
    destination_file = open(file_name, "wb")
    if drive_file_exists(slug_name):
        headers = {
            'Authorization': 'Bearer ' + access_token(),
        }
        response = requests.get(
            f"https://www.googleapis.com/drive/v3/files/{file_id}/?alt=media&supportsAllDrives=true",
            headers=headers, timeout=10)
        destination_file.write(response.content)
        if response.status_code == 200:
            destination_file.close()
            settings.uploading_data_cache.pop(name)
            return name.replace(".zip","",1)
        else:
            logger.error(response.json())
            settings.uploading_data_cache.pop(name)
            return False
    else:
        settings.uploading_data_cache.pop(name)
        return False

def count_backup_drive():
    count_drive = 0
    for file in settings.drive_data_cache:
        if file["mimeType"] == "application/x-zip-compressed":
            count_drive += 1
    return count_drive  

def drive_retained():
    retained_drive = 0
    for file in settings.drive_data_cache:
        if file["mimeType"] == "application/x-zip-compressed":
            if converting.str_to_bool(file["appProperties"]["RETAINED"]):
                retained_drive += 1
    return retained_drive

def name_from_slug(slug):
    for file in settings.drive_data_cache :
        if file["mimeType"] == "application/x-zip-compressed":
            if file["appProperties"]["SLUG"] == slug:
                return file["name"]
    return False

def delete_file(file_id):
    try:
        delete_request = requests.delete(f"https://www.googleapis.com/drive/v3/files/{file_id}?access_token=" + access_token())
        settings.refresh_drive_data = True
        return True
    except:
        settings.refresh_drive_data = True
        return False

def get_file_id(slug_name):
    for file in settings.drive_data_cache:
        if file["mimeType"] == "application/x-zip-compressed":
            if file["appProperties"]["SLUG"] == slug_name or file["appProperties"]["NAME"] == slug_name:
                return file["id"]
    return False

def drive_file_exists(slug_name):
    list_exists = [a['name'] for a in settings.drive_data_cache if a["appProperties"]["SLUG"]==slug_name or a["name"]==slug_name]
    try:
        list_exists[0]
        return True
    except:
        return False


def folder_size():
    all_size = 0
    for i in settings.drive_data_cache:
        all_size = all_size + int(i["size"])
    return all_size
