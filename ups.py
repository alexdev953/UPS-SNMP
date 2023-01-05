import logging
import time
from dataclasses import dataclass, fields
from logging.handlers import TimedRotatingFileHandler

import requests
from requests.auth import HTTPBasicAuth

# Logger Config
LOGGER_NAME = 'UPS-Logger'
LOGGER_FMT = '%(asctime)s %(name)s - %(levelname)s - %(message)s'
LOGGER_TIME_FMT = '[%d-%m-%Y %H:%M:%S]'
LOGGER_FILE_NAME = 'ups.log'

LOGGER_LEVEL = logging.INFO

logger = logging.getLogger(LOGGER_NAME)
logger.setLevel(LOGGER_LEVEL)
formatter = logging.Formatter(LOGGER_FMT, LOGGER_TIME_FMT)

console_log = logging.StreamHandler()
console_log.setFormatter(formatter)
logger.addHandler(console_log)

file_log = TimedRotatingFileHandler(LOGGER_FILE_NAME, when='d', backupCount=5, encoding='utf-8')
file_log.setFormatter(formatter)
logger.addHandler(file_log)

# SNMP web server url
URL = ''

# SNMP web server config
LOGIN = ''
PASSWORD = ''

# Telegram config
BOT_TOKEN = ''
TELEGRAM_ID_L = ['12345678', '123456789']

# Session config
session = requests.Session()

session.auth = HTTPBasicAuth(LOGIN, PASSWORD)


@dataclass
class UPS:
    mode: str
    temperature: float | str
    battery_voltage: float | str
    current_out: float | str
    volt_out: float | str
    load_level: int | str
    power_out: float = 0

    def __post_init__(self):
        for field in fields(self):
            value = getattr(self, field.name)
            if field.name in ['temperature', 'battery_voltage', 'current_out', 'volt_out']:
                setattr(self, field.name, int(value) / 10)
            elif field.name in ['load_level']:
                setattr(self, field.name, int(value))
        self.power_out = round(float(self.current_out * self.volt_out), 2)


def send_message(data: UPS, header: None | str = None):
    text = f"🏷 <b>{header}</b>\n" \
           f"⚙️ Режим роботи: <b>{data.mode}</b>\n" \
           f"🌡 Температура Упса: <b>{data.temperature}</b>\n" \
           f"🔋 Напруга батарей: <b>{data.battery_voltage}</b> V\n" \
           f"💥 Струм, вихід: <b>{data.current_out}</b> A\n" \
           f"🔌 Напруга, вихід: <b>{data.volt_out}</b> V\n" \
           f"⚖️ Навантаження: <b>{data.load_level}</b> %\n" \
           f"💡 Вихідна потужність: <b>{data.power_out}</b> W\n"
    for t_id in TELEGRAM_ID_L:
        try:
            requests.post(f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage",
                          params={"chat_id": t_id, "text": text, "parse_mode": "HTML"},
                          timeout=3)
        except Exception as e:
            logger.error(f"Помилка при відправці повідомлення: {e}")
            continue

def get_data() -> UPS:
    resp = session.get(URL)
    text_resp = resp.text
    data = text_resp.replace('\n\n', '').split('\n')
    return UPS(mode=data[0], temperature=data[1], battery_voltage=data[7],
               current_out=data[34], volt_out=data[14], load_level=data[16])


first_msg = False
voltage: int
last_voltage: float = 0.0


def check_voltage(first, second):
    if (first - second) >= 1:
        return True
    else:
        return False


while True:
    ups = get_data()
    logger.info(ups)
    if ups.mode != 'Line Mode':
        if not first_msg:
            logger.warning(f'Зміна режиму роботи: : {ups.mode}')
            send_message(ups, header="Зміна режиму роботи")
        if check_voltage(last_voltage, ups.battery_voltage) and first_msg:
            send_message(ups, header="Зміна напруги батарей")
        first_msg = True
    elif ups.mode == 'Line Mode' and first_msg:
        logger.warning(f'Зміна режиму роботи: : {ups.mode}')
        first_msg = False
        send_message(ups, header="Зміна режиму роботи")
    elif ups.load_level >= 80:
        send_message(data=ups, header="Велика нагрузка!!!!")
        logger.critical(f'Велика нагрузка: {ups.load_level}')
    last_voltage = ups.battery_voltage
    time.sleep(30)
