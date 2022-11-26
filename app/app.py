import os
import base64
import json
import urllib
import threading
from flask import Flask,request,send_file,render_template,send_from_directory,jsonify,Response
import logger
import schedule
import drive_requests
import google_api
import get_status
import settings
import backups
last_log_index = 0
template_dir = os.path.abspath('./static/')
app = Flask(__name__, template_folder=template_dir)
app.config['JSONIFY_PRETTYPRINT_REGULAR'] = True
app.config['SEND_FILE_MAX_AGE_DEFAULT'] = 0
logger.LOG_FILE = settings.LOG_FILE

def create_app():
    app.run(debug=True, use_reloader=False)

if __name__ == "__main__":
    app.run(debug=True, use_reloader=False)

def return_html(text):
    return f'<body style="background-color:Black;"><p style="color:White">{text}</p></body>'

@app.route('/favicon.ico')
def favicon():
    return send_from_directory( "logo", "favicon.ico", as_attachment=False )

@app.route('/backup', methods = ['GET', 'POST'])
def backup():
    name = request.args.get("custom_name","")
    retain_ha = request.args.get("retain_ha", False,type=bool) == "true"
    retain_drive = request.args.get("retain_drive", False,type=bool) == "true"
    new_note = request.args.get("note","")
    name=urllib.parse.unquote(name.encode("utf8"))
    new_note=urllib.parse.unquote(new_note.encode("utf8"))
    answer = backups.request(name,note=new_note,retain_ha=retain_ha,retain_drive=retain_drive)
    return jsonify({"message": f"Requested backup '{answer}'"})

@app.route('/bootstrap')
def bootstrap():
    if len(settings.last_bootstrap_data) > 2:
        bootstrap_data = settings.last_bootstrap_data
    else:
        bootstrap_data = get_status.get_bootstrap()
    data = f"bootstrap_update_data = {str(json.dumps(bootstrap_data, indent=4, sort_keys=True))};"
    return Response(data, mimetype='text/javascript')

@app.route('/getstatus')
def getstatus():
    json_ret = get_status.get_bootstrap()
    return jsonify(json_ret)

default_context = {
    "backgroundColor": google_api.generate_config()["config"]["background_color"],
    "accentColor": google_api.generate_config()["config"]["accent_color"],
    "save_drive_creds_path": "token",
    "version": 108,
    "coordEnabled": True,
    "showOpenDriveLink": True
}

@app.route('/')
def index():
    path_to_credentials = google_api.settings.DATA_FOLDER+'credentials.dat'
    if os.path.exists(path_to_credentials) is True and os.stat(path_to_credentials).st_size > 0:
        return render_template(
            'working.jinja2',
            **default_context
            )
    return render_template(
            'index.jinja2',
            **default_context
            )

@app.route("/reauthenticate")
def reauthenticate():
    return render_template(
            'index.jinja2',
            **default_context
            )

@app.route('/makeanissue', methods = ['GET', 'POST'])
def makeanissue():
    return jsonify({
    "markdown": "**Hello World**",
    "message": "Thnk you for your time"
    })

@app.route('/startSync', methods = ['POST'])
def startsync():
    return jsonify({"message": "Syncing..."})

@app.route('/getconfig', methods = ['GET', 'POST'])
def getconfig():
    return_json = google_api.generate_config()
    return return_json

@app.route('/saveconfig', methods = ['POST'])
def saveconfig():
    data = request.get_json()
    google_api.save_config(data)
    return jsonify({"message": "Config Saved"})

@app.route('/token', methods = ['POST', 'GET'])
def token():
    base64_creds = request.args.get('creds', default = 'none', type = str)
    # redirect_url = request.args.get('host', default = 'none', type = str)
    if len(str(base64_creds)) > 500:
        creds = base64.b64decode(base64_creds)
        google_json = creds.decode("utf-8")
        with open(settings.DATA_FOLDER + "credentials.dat", "w", encoding="utf-8") as f:
            f.write(google_json)
        return jsonify({"message": "Success"})
    else:
        return return_html("Plese supply more required parameters."), 400

@app.route("/log", methods = ['POST', 'GET'])
def log():
    format_type = request.args.get('format', default = 'download', type = str)
    catchup = request.args.get('catchup', default = False, type = bool)  
    if format_type == 'download':
        return send_file(settings.LOG_FILE, as_attachment=True, download_name="Backup_log.txt")
    headers = ""
    if format_type == "view":
        return render_template(
                "logs.jinja2",
                bmc_logo_path= "static/" + settings.PROGRAMM_VERSION + "/images/bmc.svg", 
                **default_context
                )
    if not catchup:
        settings.last_log_index = 0
    if format_type == "html":
        content_type = 'text/html'
    else:
        content_type = 'text/plain'
        headers = {'Content-Disposition': 'attachment; filename="backup.log"'}
    def log_level(line):
        log_colors={
            "DEBUG": "console-debug",
            "WARN": "console-warning",
            "ERROR": "console-error",
            "CRITICAL": "console-critical"
            }
        for color in log_colors[0]:
            if color[0] in line:
                return log_colors[0][color]
        return "console-default"
    def content():
        if format_type == "html":
            yield "<html><head><title>Backup Log</title></head><body><pre>\n"
        while True:
            if sum(1 for _ in open(settings.LOG_FILE,encoding="utf-8")) == settings.last_log_index:
                break
            log_file = open(settings.LOG_FILE,encoding="utf-8")
            lines=log_file.readlines()
            try:
                line = lines[settings.last_log_index]
            except IndexError:
                num_log_linbes = sum(1 for _ in open(settings.LOG_FILE,encoding="utf-8"))
                logger.error(f"Log line {settings.last_log_index} from {num_log_linbes} missing")
            yield "<span class='" + log_level(line) + "'>" + line.replace("\n", "   \n") + "</span>"
            settings.last_log_index += 1
        if format_type == "html":
            yield "</pre></body>\n"
    return app.response_class(content(), mimetype=content_type, headers=headers)

@app.route("/download")
def download():
    slug = request.args.get("slug","")
    if any(not c.isalnum() for c in slug) or len(slug) != 8:
        return jsonify({"http_status":500,"error_type":"generic_error","message":"Slug invalid"})
    name = backups.get_name(slug)
    if not name:
        drive_requests.download(slug)
        name = backups.get_name(slug)
    if name:
        filename = backups.get_filename(name)
        return send_file(filename)

@app.route("/retain", methods = ['POST', 'GET'])
def retain():
    if request.method == "POST":
        slug = request.json.get("slug","")
        sources = request.json.get("sources","")
    else:
        slug = request.args.get("slug","")
        sources = request.args.get("sources","")
        sources=urllib.parse.unquote(sources.encode("utf8"))
        try:
            sources = json.loads(sources.replace("'", "\""))
        finally: 
            sources = []
    if any(not c.isalnum() for c in slug) and len(slug) != 8:
        return jsonify({"http_status": 500, "error_type": "generic_error", "message": "Slug is invalid"})
    if "HomeAssistant" in sources:
        local_backup = threading.Thread(target=backups.set_retention, args=(slug,sources["HomeAssistant"],))
        local_backup.start()
    if "GoogleDrive" in sources:
        retained_drive = sources["GoogleDrive"]
        drive_requests.set_retention(slug,retained_drive)
    return jsonify({"message": "Updated the backup's settings"})

@app.route("/deleteSnapshot", methods = ['POST', 'GET'])
def deleteSnapshot():
    if request.method == "POST":
        slug = request.json.get("slug","")
        sources = request.json.get("sources","")
    else:
        slug = request.args.get("slug","")
        sources = request.args.get("sources","")
        sources=urllib.parse.unquote(sources.encode("utf8"))
        try:
            sources = json.loads(sources.replace("'", "\""))
        finally: 
            sources = []
    delete_ha = "HomeAssistant" in sources
    delete_drive = "GoogleDrive" in sources
    if len(sources) < 1:
        return jsonify({"http_status": 500, "error_type": "generic_error", "message": "No sources specified"})
    if any(not c.isalnum() for c in slug) and len(slug) != 8:
        return jsonify({"http_status": 500, "error_type": "generic_error", "message": "Slug is invalid"})
    message = "Generic error occurred"
    success = False
    if delete_ha:
        success, message = backups.delete(slug)
    if delete_drive:
        if drive_requests.drive_file_exists(slug):
            file_id = drive_requests.get_file_id(slug)
            drive_requests.delete_file(file_id)
            if not delete_ha:
                success = True
        else:
            message += "Backup does not exist in GDrive"
            success = False
    if success:
        return jsonify({"message": "Deleted from {0} place{1}".format((len(sources)),str("" if len(sources) <= 1 else "(s)"))})
    return jsonify({"http_status": 500, "error_type": "generic_error", "message": message})

@app.route("/upload", methods=["POST", "GET"])
def upload():
    friendly_name = "Backup"
    slug = request.args.get("slug","")
    if len(slug) != 8:
        return jsonify({"message": "Slug is invalid"})
    drive_exists = drive_requests.drive_file_exists(slug)
    name = backups.get_name(slug)
    if name:
        local_exists = os.path.isfile(os.path.join(settings.BACKUP_FOLDER,name+ ".zip"))
        if local_exists and drive_exists:
            return jsonify({"message": "Backup already in both places"})
    if drive_exists:
        friendly_name = drive_requests.download(slug)
        return jsonify({"message": f"Downloaded {friendly_name} from Google drive"})
    
    if local_exists:
        drive_requests.upload_file(name)
        return jsonify({"message": f"Uploaded {name} to Google drive"})

    return jsonify({"message": "Backup not found"})
         
@app.route("/broken")
def broken():
    return return_html("File does not exist."), 404

@app.route("/logo/<path:filename>")
def logo(filename):
    filename = "./logo/" + os.path.basename(filename) 
    if os.path.isfile(filename+".png"):
        return send_file(filename+".png")
    if os.path.isfile(filename+".svg"):
        return send_file(filename+".svg")
    return return_html("File does not exist."), 404

@app.route("/note", methods = ['POST', 'GET'])
def note():
    if request.method == "POST":
        slug = request.json.get("slug","")
        new_note = request.json.get("note","")
    else:
        slug = request.args.get("slug","")
        new_note = request.args.get("note","")
    new_note=urllib.parse.unquote(new_note.encode("utf8"))
    drive_requests.set_note(slug,new_note,)
    backups.set_note(slug, new_note,)
    return jsonify({"message": "Updated the backup's note"})
