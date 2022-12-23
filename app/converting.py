"""
Converts various values into strings.
"""
import re
import datetime

def human_to_seconds(string):
    """
    Tries to find size string and values to calculate the size to seconds.
    """
    type_string_list = ["seconds","minute", "hour", "day", "month", "year"]
    times_list_for_type = [1,60,60*60,60*60*24,60*60*24*30.43685,60*60*24*365]
    seconds = 0
    if str(string).isdigit():
        return int(string)
    for parts in re.findall(r'\d*\D+',str(string)):
        for type_string in type_string_list:
            if type_string in str.lower(parts):
                index = type_string_list.index(type_string)
                number = [int(s) for s in parts.split() if s.isdigit()][0]
                #try:
                #    number = [int(s) for s in parts.split() if s.isdigit()][0]
                #except Exception:
                #    number = ""
                #    for split in parts:
                #        if split.isdigit():
                #            number = number + split
                #    number = int(number)
                loop_seconds = number*times_list_for_type[index]
                seconds = seconds + loop_seconds
    return int(seconds)

def seconds_to_human(string, single=False):
    """
    Converts seconds to human readable string.
    """
    return_string = ""
    comma_months = ""
    comma_days = ""
    comma_hours = ""
    comma_minutes = ""
    comma_seconds = ""
    left_seconds = 0
    string = str(string).split(".", maxsplit=1)[0]
    left_seconds = int(string) if str(string).isdigit() else human_to_seconds(string)
    years = int(left_seconds//(60*60*24*365))
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
        left_seconds = left_seconds -int(years * 60*60*24*365)
    months = int(left_seconds//2629743)
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
        left_seconds = left_seconds -int(months * 2629743.83)
    days = int(left_seconds//(60*60*24))
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
        left_seconds = left_seconds - int(days * 60*60*24)
    hours = int(left_seconds//(60*60))
    if hours >= 1:
        hours_string = "hours"
        comma_minutes = ", "
        comma_seconds = ", "
        if hours == 1:
            hours_string = "hour"
        if single:
            return f"{hours} {hours_string}"
        return_string= f"{return_string}{comma_hours}{hours} {hours_string}"
        left_seconds = left_seconds - int(hours * 60*60)
    minutes = int(left_seconds//60)
    if minutes >= 1:
        minutes_string = "minutes"
        comma_seconds = ", "
        if minutes == 1:
            minutes_string = "minute"
        if single:
            return f"{minutes} {minutes_string}"
        return_string= f"{return_string}{comma_minutes}{minutes} {minutes_string}"
        left_seconds = left_seconds -int(minutes * 60)
    if  left_seconds > 0:
        seconds_string = "seconds"
        if left_seconds == 1:
            seconds_string = "second"
        if single:
            return f"{left_seconds} {seconds_string}"
        return_string= f"{return_string}{comma_seconds}{left_seconds} {seconds_string}"
    return return_string

def human_to_bytes(string):
    """
    Tries to find size string and values to calculate the size to seconds.
    """
    string = str(string)
    unit_list = ["b","kb","mb","gb","tb","pb"]
    index = 0
    for unit_suffix in unit_list:
        if unit_suffix in string.lower():
            index = unit_list.index(unit_suffix)
            break
    integer = int("".join([c for c in string if c.isdigit()]))
    integer = integer * (1024**index)
    return integer

def bytes_to_human(size_start, decimal_places=1, convert_type="short"):
    """
    Tries to find size string and values to calculate the size to bytes.
    """
    if not str(size_start).isdigit():
        size_start = human_to_bytes(size_start)
    size = int(size_start)
    power = 2**10
    unit = 0
    power_labels = {0 : 'B', 1: 'KB', 2: 'MB', 3: 'GB', 4: 'TB'}
    if convert_type == "long":
        power_labels = {0 : 'bytes', 1: 'kilobytes', 2: 'megabytes', 3: 'gigabytes', 4: 'terabytes'}
    while size > power:
        size /= power
        unit += 1
    size = f"{size:.{decimal_places}f}".rstrip("0").rstrip(".")
    return f"{size} {power_labels[unit]}"

def timestamp_to_timestring(timestamp=0):
    """
    Turn a integer into a timestamp.
    """
    return datetime.datetime.fromtimestamp(timestamp)

def str_to_bool(origin_str,default=False):
    """
    Checks if a string is a contains a boolean string.
    """
    if isinstance(origin_str,bool):
        return origin_str
    if "false" in origin_str.lower() and "true" in origin_str.lower():
        return default
    elif "true" in origin_str.lower():
        return True
    elif "false" in origin_str.lower():
        return False
    return default
