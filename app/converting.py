import re, datetime
def human_to_seconds(string):
    type_string_list = ["seconds","minute", "hour", "day", "month", "year"]
    times_list_for_type = [1,60,60*60,60*60*24,60*60*24*30.43685,60*60*24*365]
    seconds = 0
    if str(string).isdigit():
        return str(string)
    for parts in re.findall('\d*\D+',str(string)):
        for type in type_string_list:
            if type in str.lower(parts):
                index = type_string_list.index(type)
                try:
                    number = [int(s) for s in parts.split() if s.isdigit()][0]
                except:
                    number = ""
                    for s in parts:
                        if s.isdigit():
                            number = number + s
                    number = int(number)
                loop_seconds = number*times_list_for_type[index]
                seconds = seconds + loop_seconds
    return int(seconds)

def seconds_to_human(string, single=False):
    return_string = ""
    comma_months = ""
    comma_days = ""
    comma_hours = ""
    comma_minutes = ""
    comma_seconds = ""
    left_seconds = 0
    string = str(string).split(".")[0]
    if not str(string).isdigit():
        try:
            left_seconds = human_to_seconds(string)
        except:
            pass
    else: 
        left_seconds = int(string)
    
    years = int(str(int(left_seconds)//(60*60*24*365)).split(".")[0])
    if years >= 1 and left_seconds >= (60*60*24*365) :
        years_string = "years"
        comma_months = ", "
        comma_days = ", "
        comma_hours = ", "
        comma_minutes = ", "
        comma_seconds = ", "
        if years == 1:
            years_string = "year"
        if single:
            return f"{years} {years_string}"
        return_string= f"{years} {years_string}"
        left_seconds = left_seconds -int(str((years * (60*60*24*365))).split(".")[0])
    
    months = int(str((int(left_seconds)//(2629743))).split(".")[0]) #2629743.83
    if months >= 1:
        months_string = "months"
        comma_days = ", "
        comma_hours = ", "
        comma_minutes = ", "
        comma_seconds = ", "
        if months == 1:
            months_string = "month"
        if single:
            return f"{months} {months_string}"
        return_string= f"{return_string}{comma_months}{months} {months_string}"
        left_seconds = left_seconds -int(str((months * (2629743.83))).split(".")[0])

    days = int(str(int(left_seconds)//(60*60*24)).split(".")[0])
    if days >= 1:
        days_string = "days"
        comma_hours = ", "
        comma_minutes = ", "
        comma_seconds = ", "
        if days == 1:
            days_string = "day"
        if single:
            return f"{days} {days_string}"
        return_string= f"{return_string}{comma_days}{days} {days_string}"
        left_seconds = left_seconds -(days * (60*60*24))

    hours = int(str(int(left_seconds)//(60*60)).split(".")[0])
    if hours >= 1:
        hours_string = "hours"
        comma_minutes = ", "
        comma_seconds = ", "
        if hours == 1:
            hours_string = "hour"
        if single:
            return f"{hours} {hours_string}"
        return_string= f"{return_string}{comma_hours}{hours} {hours_string}"
        left_seconds = left_seconds -int(str((hours * (60*60))).split(".")[0])
    
    minutes = int(str(int(left_seconds)//60).split(".")[0])
    if minutes >= 1:
        minutes_string = "minutes"
        comma_seconds = ", "
        if minutes == 1:
            minutes_string = "minute"
        if single:
            return f"{minutes} {minutes_string}"
        return_string= f"{return_string}{comma_minutes}{minutes} {minutes_string}"
        left_seconds = left_seconds -int(str((minutes * 60)).split(".")[0])
    if  left_seconds > 0:
        seconds_string = "seconds"
        if left_seconds == 1:
            seconds_string = "second"
        if single:
            return f"{left_seconds} {seconds_string}"
        return_string= f"{return_string}{comma_seconds}{left_seconds} {seconds_string}"
    return return_string

def human_to_bytes(string):
    string = str(string)
    list = ["'*!'","kb","mb","gb","tb","pb"]
    index = 0
    for type in list:
        if type in string.lower():
            index = list.index(type)
            break
    integer = 1.0
    for s in string.split():
        try:
            integer = float(s)
        except:
            pass
    if index > 0:
        integer = integer * (1024**index)
    return int(integer)

def bytes_to_human(size_start, decimal_places=1, type="short"):
    if not str(size_start).isdigit():
        size_start = human_to_bytes(size_start)
    size = int(size_start)
    power = 2**10
    n = 0
    power_labels = {0 : 'B', 1: 'KB', 2: 'MB', 3: 'GB', 4: 'TB'}
    if type == "long":
        power_labels = {0 : 'bytes', 1: 'kilobytes', 2: 'megabytes', 3: 'gigabytes', 4: 'terabytes'}
    while size > power:
        size /= power
        n += 1
    size = f"{size:.{decimal_places}f}".rstrip("0").rstrip(".")
    return f"{size} {power_labels[n]}"

def timestamp_to_timestring(timestamp=0):
    return datetime.datetime.fromtimestamp(timestamp)

def str_to_bool(str):
    if "true" in str.lower():
        return True
    return False