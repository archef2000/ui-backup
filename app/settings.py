DATA_FOLDER = "./../data/"
SOURCE_FOLDER = "./../source/"
BACKUP_FOLDER = "./../backups/"
DRIVE_FOLDER_NAME = "Docker Backup 2"
HABACKUP_AUTHENTICATION_URL = "https://habackup.io/drive/authorize"
LOG_LEVEL = "info"
LOG_FILE = "log.txt"
PROGRAMM_VERSION = "108"
last_log_index = 0
backup_running = False
www_googleapis_com_ping_out = ""
backup_schedule_running = False
last_bootstrap_data = ""
uploading_data_cache = {}
downloading_data_cache = {}
running_backup_info = {}
SELECT_FIELDS = "id,name,appProperties,size,trashed,mimeType,modifiedTime,capabilities,parents,driveId"
drive_file_list = []
refresh_drive_data = True
drive_data_cache = {}
gdrive_info = {
    "user_email":"",
    "quotaBytesUsed":0,
    "quotaBytesTotal":0
}
bootstrap_functions_data = {}
# Type:        10x sec: bytes:     1x sec:  size in MB:
# ZIP_STORED   10.376 # 28489628 # 1.048  # 27.2 MB
# ZIP_DEFLATED 16.021 # 8809296  # 1.588  # 8.4 MB
# ZIP_BZIP2    31.922 # 7457568  # 3.166  # 7.1 MB
# ZIP_LZMA     85.082 # 6257064  # 8.185  # 6 MB
ZIP_COMPRESSION = "pyzipper.ZIP_DEFLATED" # / ZIP_BZIP2
