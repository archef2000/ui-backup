"""
A python programm for managing backups in Google Drive.
"""
import json
import urllib.parse
import math
import datetime
import time
import os
import base64
import requests
import logger
import pyzipper
import get_status
import settings
import converting

BASE_CHUNK_SIZE = 256 * 1024
CHUNK_SIZE = 8 * BASE_CHUNK_SIZE
CHUNK_SIZE = 4 * BASE_CHUNK_SIZE

def valid_access_token():
    """
    Check if the stored access token is valid.

    A valid access token is one that has not yet expired.
    The expiration date is checked against the current time, with a 5-minute buffer.
    """
    credentials_file_path = os.path.join(settings.DATA_FOLDER,"credentials.dat")
    if not os.path.isfile(credentials_file_path):
        return False
    with open(credentials_file_path, 'r', encoding="utf-8") as credentials_file:
        data = json.load(credentials_file)
    token_expiry = datetime.datetime.strptime(data['token_expiry'],"%Y-%m-%dT%H:%M:%SZ")
    return token_expiry > datetime.datetime.utcnow() + datetime.timedelta(minutes=5)

def access_token():
    """
    Get the current access token.

    If the current access token is not valid attempt to refresh the access token.
    """
    credentials_file_path = os.path.join(settings.DATA_FOLDER,"credentials.dat")
    with open(credentials_file_path, 'r', encoding="utf-8") as credentials_file:
        data = json.load(credentials_file)
    if valid_access_token():
        return data.get('access_token',False)
    refresh_token = data.get('refresh_token')
    data = requests.post(
        'https://habackup.io/drive/refresh',
        json={"refresh_token": refresh_token},
        timeout=10).json()
    new_access_token = data.get('access_token',False)
    with open(credentials_file_path, 'w', encoding="utf-8") as credentials_file:
        json.dump(data, credentials_file)
    return new_access_token

def folder_id():
    """
    Get the ID of the folder used for storing data.

    If a folder ID has been previously stored in the "folder.dat" file, that ID is returned.
    It also checks if the folder already exists in the user's Google Drive.
    If such a folder exists, its ID is returned.
    If no such folder exists, a new folder is created and its ID is returned.
    """
    folder_id_file_path = os.path.join(settings.DATA_FOLDER, "folder.dat")
    if os.path.exists(folder_id_file_path):
        with open(folder_id_file_path, encoding="utf-8") as folder_id_file:
            folderid = folder_id_file.read()
            if len(folderid) == 33:
                return folderid
    existing_folder_id = drive_folder_exists()
    if existing_folder_id:
        return existing_folder_id
    else:
        return create_drive_folder()

def get_filename(name):
    """
    Check if the given name exists in the BACKUP_FOLDER.
    """
    filename = os.path.join(settings.BACKUP_FOLDER, name)
    if os.path.isfile(filename):
        return filename
    if os.path.isfile(filename+".zip"):
        return filename+".zip"
    return False

def create_drive_folder():
    """
    Creates a new folder in Google Drive and returns the folder's ID.
    The ID of the created folder is also stored in a file in the DATA_FOLDER specified in settings.
    """
    headers = {
        'Authorization': 'Bearer ' + access_token(),
        'Content-Type': 'application/json; charset=UTF-8'
    }
    data = {
        "name": settings.DRIVE_FOLDER_NAME,
        "mimeType": "application/vnd.google-apps.folder",
    }
    data_json = json.dumps(data)
    response = requests.post(
        'https://www.googleapis.com/drive/v3/files',
        headers=headers,
        data=data_json,
        timeout=10 ).json()
    new_folder_id = response['id']
    with open(os.path.join(settings.DATA_FOLDER,"folder.dat"),'w',encoding="utf-8") as folderid:
        folderid.write(new_folder_id)
    return new_folder_id

def drive_folder_exists():
    """
    Checks if a folder exists in Google Drive and returns the folder's ID if it exists.
    If the folder exists, the ID of the folder is also stored in a file.
    """
    params = {
        "name": settings.DRIVE_FOLDER_NAME,
        "mimeType": "application/vnd.google-apps.folder",
        "trashed": False,
    }
    base_url = "https://www.googleapis.com/drive/v3/files"
    query_string = query_encode(params,"files(id,trashed,name)")
    url = f"{base_url}?{query_string}"
    headers = {"Authorization": "Bearer " + access_token()}
    data = requests.get(url, headers=headers, timeout=10).json()
    folder_id_path = os.path.join(settings.DATA_FOLDER, "folder.dat")
    if len(data["files"]) > 0:
        new_folder_id = data["files"][0].get("id",False)
        with open(folder_id_path, 'w', encoding="utf-8") as folderid:
            folderid.write(new_folder_id)
        return new_folder_id
    else:
        return False

def query_encode(query_json, fields=False):
    """
    Encodes a dictionary into a query string for Google Drive.
    """
    query = " and ".join(f"{k}={v}" if isinstance(v,
                    bool) else f"{k}=\"{v}\"" for k,v in query_json.items())
    return_query = f"q={urllib.parse.quote(query)}"
    if fields:
        return_query += f"&fields={fields}"
    return return_query

def get_free_space():
    """
    Returns the free space in bytes of Google Drive.
    """
    base_url = "https://www.googleapis.com/drive/v2/about"
    params = {
        "fields": "quotaBytesTotal,quotaBytesUsed",
    }
    query_string = urllib.parse.urlencode(params)
    url = f"{base_url}?{query_string}"
    headers = {"Authorization": "Bearer " + access_token()}
    with requests.get(url, headers=headers, timeout=10) as response:
        data = response.json()
        bytes_total = data['quotaBytesTotal']
        bytes_used = data['quotaBytesUsed']
        free_space = int(bytes_total) - int(bytes_used)
        return free_space, bytes_used

def upload_session_url(filename,retained=False):
    """
    Returns the upload session URL for the given filename.
    Ans is then used for the chunked upload.
    """
    file_name = get_filename(filename)
    file_size = str(os.path.getsize(file_name))
    headers = {
        "Authorization": "Bearer " + access_token(),
        "Content-Type": "application/json; charset=UTF-8",
        "X-Upload-Content-Type": "application/x-zip-compressed",
        "X-Upload-Content-Length": file_size,
        "X-Upload-Content-Range": f"bytes 0-{file_size}/{file_size}",
    }
    querystring = {"uploadType": "resumable"}
    with pyzipper.AESZipFile(file_name) as zip_file:
        backup_json_data = json.loads(zip_file.read("info.json"))
        note = zip_file.read("note.txt").decode() if "note.txt" in zip_file.namelist() else None
        folders = get_status.zip_file_folders(zip_file)
    if not os.path.isfile(os.path.join(settings.BACKUP_FOLDER,filename)):
        filename += ".zip"
    with open("logo/drive_logo.png","rb") as logo_file:
        urlsafe_logo = base64.urlsafe_b64encode(logo_file.read()).decode('utf8')
    drive_creation_time = datetime.datetime.fromtimestamp(
        backup_json_data["timestamp"]).strftime("%Y-%m-%dT%H:%M:%SZ")
    drive_modificition_time = datetime.datetime.fromtimestamp(
        backup_json_data["timestamp"]).strftime("%Y-%m-%dT%H:%M:%SZ")
    payload = {
        "contentHints": {
            "thumbnail": {
                "image": urlsafe_logo,
                "mimeType": "image/png"
                },
            },
        "name": filename,
        "description": "This is a backup file",
        "createdTime": drive_creation_time,
        "modifiedTime": drive_modificition_time,
        "parents": [folder_id()],
        "appProperties": {
            "SLUG": backup_json_data["slug"],
            "NAME": backup_json_data["name"],
            "PROTECTED": str(backup_json_data["protected"]),
            "TYPE": "full" if backup_json_data["exclude_folders"] == "" else "partial",
            "TIMESTAMP" : backup_json_data['timestamp'],
            "RETAINED": str(retained),
            "NOTE": "" if note is None else str(note),
            },
    }
    folder_i = 1
    for folder in folders:
        payload["appProperties"][f"FOLDER_{folder_i}"] = json.dumps(folder)
        folder_i += 1
    response = requests.post(
        'https://www.googleapis.com/upload/drive/v3/files',
        headers=headers,
        data=json.dumps(payload),
        params=querystring,
        timeout=10
    )
    if response.status_code == 200:
        session_uri = response.headers['Location']
        return session_uri
    else:
        return

def set_note(file_id_slug, new_note):
    """
    Sets the note for the given file_id_slug.
    """
    if len(file_id_slug) == 8:
        file_id_slug = get_file_id(file_id_slug)
    base_url = f"https://www.googleapis.com/drive/v3/files/{file_id_slug}"
    params = {
        "fields": "appProperties",
        "supportsAllDrives": "true",
    }
    url = f"{base_url}?{urllib.parse.urlencode(params)}"
    headers = {'Authorization': 'Bearer '+access_token(),}
    new_note = "" if new_note is None else str(new_note)
    data = {
        'appProperties': {'NOTE': new_note,},
        'description': new_note,
    }
    response = requests.patch(url, headers=headers, json=data, timeout=10)
    settings.refresh_drive_data = True
    return response.status_code < 400

def set_retention(file_id_slug, retention):
    """
    Sets the retention value for the file with the given file ID or slug.

    If the slug is provided, it is converted to the file ID using the get_file_id() function.

    If the file ID is not found, the function returns False.

    Args:
    file_id_slug (str): The file ID or slug of the file.
    retention (str): The retention value to set.
    """
    retention = str(retention)
    if len(file_id_slug) == 8:
        file_id_slug = get_file_id(file_id_slug)
    if not file_id_slug:
        return False
    base_url = f"https://www.googleapis.com/drive/v3/files/{file_id_slug}"
    params = {
        "fields": "appProperties",
        "supportsAllDrives": "true",
    }
    url = f"{base_url}?{urllib.parse.urlencode(params)}"
    headers = {'Authorization': 'Bearer '+access_token(),}
    data = {
        'appProperties': {'RETAINED': retention,},
        'description': retention,
    }
    response = requests.patch(url, headers=headers, json=data, timeout=10)
    settings.refresh_drive_data = True
    return response.status_code == 200

def upload_file(filename,retained=False):
    """
    Uploads a file to Google Drive with a session ID.
    If the size of the file is bigger than 5MB a chunked upload is used instead.
    """
    settings.uploading_data_cache[filename] = {
        "name": "Google Drive",
        "started": time.time(),
        "speed": 0,
        "progress": 0
    }
    file_name = get_filename(filename)
    file_size = os.path.getsize(file_name)
    session_uri = upload_session_url(filename,retained)
    with open(file_name, "rb") as in_file:
        binary_file = in_file.read()
    if file_size <= 5242880:
        headers = {
            'Content-Length': str(file_size),
            'Content-Type': "application/x-zip-compressed"
        }
        response = requests.request(
            "PUT", session_uri, data=binary_file, headers=headers, timeout=10)
        settings.uploading_data_cache.pop(filename)
        settings.refresh_drive_data = True
        return response.content
    else:
        upload_start = time.time()
        total_bytes = file_size
        first_byte = 0
        last_byte = CHUNK_SIZE - 1
        times = int(math.ceil(file_size/CHUNK_SIZE))
        for _ in range(times):
            if last_byte > total_bytes:
                last_byte = total_bytes -1
            elapsed_time = settings.uploading_data_cache[filename]["started"]
            upload_speed = first_byte/(time.time() - elapsed_time)
            settings.uploading_data_cache[filename]["progress"] = (first_byte/file_size)*100
            settings.uploading_data_cache[filename]["speed"] = upload_speed
            chunk = binary_file[first_byte:last_byte+1]
            headers = {
                'Content-Length': str(total_bytes),
                'Content-Type': "application/x-zip-compressed",
                'Content-Range': f"bytes {first_byte}-{last_byte}/{total_bytes}"
            }
            response = requests.request(
                "PUT", session_uri, data=chunk, headers=headers, timeout=10)
            if response.status_code == 200 and times-1 == _:
                elapsed_time = time.time()-upload_start
                logger.debug(
                    f"Uploaded backup {file_name} to Google Drive in {elapsed_time} seconds")
                settings.uploading_data_cache.pop(filename)
                settings.refresh_drive_data = True
                return True
            byte_range = response.headers["Range"]
            first_byte = byte_range.split("=",1)[1].split("-",1)[0]
            last_byte = byte_range.split("=",1)[1].split("-",1)[1]
            # percentage = str((int(last_byte)/file_size)*100)[:2]+"%"
            first_byte = int(last_byte)+1
            last_byte = int(first_byte)+CHUNK_SIZE

def download(slug_name):
    """
    Downloads the file with the given file ID and saves it to the BACKUP_FOLDER.
    If the file ID slug is not found, the function returns False.
    """
    name = name_from_slug(slug_name) or slug_name
    file_name = os.path.join(settings.BACKUP_FOLDER, name)
    file_id = get_file_id(slug_name)
    if not file_id:
        logger.error("File not found in Google Drive")
        return False
    settings.uploading_data_cache[name] = {
        "name": "Home Assistant",
        "started": time.time(),
        "speed": 0,
        "progress": 0
    }
    headers = {'Authorization':'Bearer '+access_token(),}
    base_url = "https://www.googleapis.com/drive/v3/files/"
    response = requests.get(
        f"{base_url}{file_id}/?alt=media&supportsAllDrives=true",
        headers=headers, timeout=10)
    with open(file_name, "wb") as destination_file:
        destination_file.write(response.content)
    settings.uploading_data_cache.pop(name)
    if response.status_code == 200:
        return name.replace(".zip","",1)
    return False

def count_backup_drive():
    """
    Count backups in Google Drive.
    """
    count_drive = sum(file["mimeType"] == "application/x-zip-compressed"
                      for file in settings.drive_data_cache
                      )
    return count_drive

def number_drive_retained():
    """
    Count all retained backups in Google Drive.
    """
    retained_drive = sum(
        file["mimeType"] == "application/x-zip-compressed" and
        converting.str_to_bool(file["appProperties"].get("RETAINED", False))
        for file in settings.drive_data_cache
    )
    return retained_drive

def name_from_slug(slug):
    """
    Get backup name from a given slug in Google Drive.
    """
    for file in settings.drive_data_cache :
        if file["mimeType"] == "application/x-zip-compressed":
            if file["appProperties"]["SLUG"] == slug:
                return file["name"]
    return False

def drive_retained_slug(slug):
    """
    Check if a backup is retained in Google Drive.
    """
    for drive_backup in settings.drive_data_cache:
        if drive_backup["appProperties"].get("SLUG", False) == slug:
            return True
    return False

def drive_retained(file_id):
    """
    Use the file id to determine if the backup is retained in Google Drive.
    """
    params = {"trashed": False,}
    base_url = "https://www.googleapis.com/drive/v3/files/"
    query_string = query_encode(params,"id,trashed,name,appProperties")
    url = f"{base_url}{file_id}?{query_string}"
    headers = {'Authorization':'Bearer '+access_token(),}
    file_json = requests.get(url,timeout=10,headers=headers).json()
    return converting.str_to_bool(file_json["appProperties"].get("RETAINED",False))

def delete_file(file_id):
    """
    Deletes the file with the given file ID from Google Drive.
    """
    if drive_retained(file_id):
        return False
    headers = {'Authorization':'Bearer '+access_token(),}
    try:
        delete_request = requests.delete(
            f"https://www.googleapis.com/drive/v3/files/{file_id}",
            timeout=10,headers=headers)
    except requests.exceptions.ReadTimeout:
        delete_request = False
    settings.refresh_drive_data = True
    return not delete_request

def get_file_id(slug_name):
    """"
    Get the Google Drive file ID associated withthe slug
    """
    for file in settings.drive_data_cache:
        app_properties = file["appProperties"]
        if file["mimeType"] == "application/x-zip-compressed":
            if app_properties["SLUG"] == slug_name or app_properties["NAME"] == slug_name:
                return file["id"]
    return False

def drive_file_exists(slug_name):
    """
    Checks if the backup is in Google Drive.
    """
    return any(a['name'] == slug_name or a['appProperties']['SLUG'] == slug_name
               for a in settings.drive_data_cache)

def folder_size():
    """
    Sum up the size of all backups in google drive
    """
    all_size = sum(int(file["size"])
                   for file in settings.drive_data_cache
                   if file["mimeType"] == "application/x-zip-compressed")
    return all_size
