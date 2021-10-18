import logging
import logging.handlers
import os
import sys
import time
from json.decoder import JSONDecodeError
from logging import StreamHandler

import requests
import telegram
from dotenv import load_dotenv

load_dotenv()

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[StreamHandler(stream=sys.stdout)]
)

PRACTICUM_TOKEN = os.getenv('PRACTICUM_TOKEN')
PRAСTIСUM_AUTH = {'Authorization': f'OAuth {PRACTICUM_TOKEN}'}
PRACTICUM_ENDPOINT = (
    'https://practicum.yandex.ru/api/user_api/homework_statuses/'
)
PRACTICUM_RETRY_TIME = 60 * 10

TELEGRAM_TOKEN = os.getenv('TELEGRAM_TOKEN')
TELEGRAM_CHAT_ID = os.getenv('TELEGRAM_CHAT_ID')


HOMEWORK_STATUSES = {
    'approved': 'Работа проверена: ревьюеру всё понравилось. Ура!',
    'reviewing': 'Работа взята на проверку ревьюером.',
    'rejected': 'Работа проверена, в ней нашлись ошибки.'
}


class HTTPStatusIsNot200(Exception):
    """Обрабатывает случай когда HTTP-ответ не равен 200."""

    pass


class ApiStatusUndocumented(Exception):
    """Обрабатывает случай недокументированного статуса ответа от API."""

    pass


def send_message(bot, message):
    """При изменении статуса домашки отправляет сообщение пользователю."""
    try:
        bot.send_message(chat_id=TELEGRAM_CHAT_ID, text=message)
    except requests.exceptions.RequestException as error:
        message = f'Сбой в работе API сервиса: {error}'
        bot.send_message(chat_id=TELEGRAM_CHAT_ID, text=message)
        logging.info(f'Сообщение об ошибке отправлено {message}')
    logging.info(f'Сообщение успешно отправлено {message}')


def get_api_answer(url, current_timestamp):
    """Отправляет запрос к API домашки на ENDPOINT."""
    try:
        payload = {'from_date': current_timestamp}
        response = requests.get(
            PRACTICUM_ENDPOINT,
            headers=PRAСTIСUM_AUTH,
            params=payload
        )
    except requests.exceptions.RequestException as error:
        logging.error(f'Сбой в работе API сервиса: {error}')
    if response.status_code != 200:
        logging.error(f'HTTPStatus is not OK: {response.status_code}')
        raise HTTPStatusIsNot200(
            f'Эндпоинт {PRACTICUM_ENDPOINT} недоступен.'
            f'Код ответа API: {response.status_code}'
        )
    try:
        return response.json()
    except JSONDecodeError as error:
        logging.error(f'Ответ от API пришел не в формате JSON: {error}')
        return {}


def parse_status(homework):
    """При изменении статуса домашки - анализирует его."""
    verdict = HOMEWORK_STATUSES[homework['status']]
    homework_name = homework['homework_name']
    return f'Изменился статус проверки работы "{homework_name}". {verdict}'


def check_response(response):
    """После запроса к API домашки проверяет не изменился ли статус."""
    homeworks = response.get('homeworks')[0]
    status = homeworks.get('status')
    if status not in HOMEWORK_STATUSES:
        logging.error(
            f'Недокументированный статус домашней работы: {status}'
        )
        raise ApiStatusUndocumented(
            f'Недокументированный статус домашней работы: {status}'
        )
    return status


def get_current_timestamp():
    """Обновляет временную метку."""
    current_timestamp = int(time.time() - PRACTICUM_RETRY_TIME)
    return current_timestamp


def check_tokens():
    """Проверка наличия переменных окружения."""
    if PRACTICUM_TOKEN and TELEGRAM_TOKEN is None:
        logging.critical(
            'Отсутствует обязательная переменная окружения.'
            'Программа принудительно остановлена.')
        exit()


def main():
    """Запуск телеграмм-бота."""
    check_tokens()
    bot = telegram.Bot(TELEGRAM_TOKEN)
    current_timestamp = int(time.time())
    errors = True
    while True:
        try:
            response = get_api_answer(PRACTICUM_ENDPOINT, current_timestamp)
            if not response.get('homeworks'):
                time.sleep(PRACTICUM_RETRY_TIME)
                continue
            check_response(response)
            message = parse_status(response.get('homeworks')[0])
            send_message(bot, message)
            time.sleep(PRACTICUM_RETRY_TIME)
            get_current_timestamp()
        except Exception as error:
            message = f'Сбой в работе телеграмм-бота: {error}'
            logging.info(f'Уведомление об ошибке отправлено в чат {message}')
            if errors:
                errors = False
                send_message(bot, message)
            time.sleep(PRACTICUM_RETRY_TIME)
            get_current_timestamp()


if __name__ == '__main__':
    main()
