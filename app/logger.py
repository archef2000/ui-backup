import datetime, inspect
from styles import colors

LOG_FILE = "log.txt"
INFO = colors.Green
ERROR = colors.Red
WARNING = colors.Yellow
DEBUG = colors.Cyan
FATAL = colors.Magenta
CRITICAL = colors.Blue

def info(message):
    curframe = inspect.currentframe()
    calframe = inspect.getouterframes(curframe, 2)
    called_from = str(calframe[1][3])
    currdate = str(datetime.datetime.now().strftime("%m-%d %H:%M:%S"))
    log_message = currdate +" INFO ["+ called_from +"] "+message
    output(log_message)
    print(INFO+ log_message +colors.ResetAll)

def error(message):
    curframe = inspect.currentframe()
    calframe = inspect.getouterframes(curframe, 2)
    called_from = str(calframe[1][3])
    currdate = str(datetime.datetime.now().strftime("%m-%d %H:%M:%S"))
    log_message = currdate +" ERROR ["+ called_from +"] "+message
    output(log_message)
    print(ERROR+ log_message +colors.ResetAll)

def warn(message):
    curframe = inspect.currentframe()
    calframe = inspect.getouterframes(curframe, 2)
    called_from = str(calframe[1][3])
    currdate = str(datetime.datetime.now().strftime("%m-%d %H:%M:%S"))
    log_message = currdate +" WARN ["+ called_from +"] "+message
    output(log_message)
    print(WARNING+ log_message +colors.ResetAll)

def debug(message):
    curframe = inspect.currentframe()
    calframe = inspect.getouterframes(curframe, 2)
    called_from = str(calframe[1][3])
    currdate = str(datetime.datetime.now().strftime("%m-%d %H:%M:%S"))
    log_message = currdate +" DEBUG ["+ called_from +"] "+message
    output(log_message)
    print(DEBUG+ log_message +colors.ResetAll)

def critical(message):
    curframe = inspect.currentframe()
    calframe = inspect.getouterframes(curframe, 2)
    called_from = str(calframe[1][3])
    currdate = str(datetime.datetime.now().strftime("%m-%d %H:%M:%S"))
    log_message = currdate +" CRITICAL ["+ called_from +"] "+message
    output(log_message)
    print(CRITICAL+ log_message +colors.ResetAll)

def output(log_message):
    f = open(LOG_FILE, "a")
    f.write("\n"+str(log_message))
    f.close()

