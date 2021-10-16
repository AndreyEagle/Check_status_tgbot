import logging
import logging.handlers
import os
import sys
import time
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
TELEGRAM_TOKEN = os.getenv('TELEGRAM_TOKEN')
CHAT_ID = os.getenv('CHAT_ID')

RETRY_TIME = 60 * 10
ENDPOINT = 'https://practicum.yandex.ru/api/user_api/homework_statuses/'

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
    bot = telegram.Bot(TELEGRAM_TOKEN)
    bot.send_message(chat_id=CHAT_ID, text=message)
    logging.info(f'Сообщение успешно отправлено {message}')


def get_api_answer(url, current_timestamp):
    """Отправляет запрос к API домашки на ENDPOINT."""
    url = ENDPOINT
    headers = {
        'Authorization': f'OAuth {PRACTICUM_TOKEN}'
    }
    payload = {'from_date': current_timestamp}
    response = requests.get(
        url,
        headers=headers,
        params=payload
    )
    if response.status_code != 200:
        logging.error(
            f'HTTPStatus is not OK: {response.status_code}')
        raise HTTPStatusIsNot200(
            f'Эндпоинт {ENDPOINT} недоступен. '
            f'Код ответа API: {response.status_code}')
    return response.json()


def parse_status(homework):
    """При изменении статуса домашки - анализирует его."""
    verdict = HOMEWORK_STATUSES.get(homework.get('status'))
    homework_name = homework.get('homework_name')
    if verdict is not None:
        return f'Изменился статус проверки работы "{homework_name}". {verdict}'


def check_response(response):
    """После запроса к API домашки проверяет не изменился ли статус."""
    homeworks = response.get('homeworks')[0]
    homework = homeworks.get('status')
    if homework not in HOMEWORK_STATUSES:
        logging.error(
            f'Недокументированный статус домашней работы: {homework}'
        )
        raise ApiStatusUndocumented(
            f'Недокументированный статус домашней работы: {homework}'
        )
    return homework


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
            response = get_api_answer(ENDPOINT, current_timestamp)
            if response.get('homeworks') == []:
                time.sleep(RETRY_TIME)
                continue
            check_response(response)
            message = parse_status(response.get('homeworks')[0])
            send_message(bot, message)
            time.sleep(RETRY_TIME)
            current_timestamp = int(time.time() - RETRY_TIME)
        except Exception as error:
            message = f'Сбой в работе телеграмм-бота: {error}'
            logging.info(f'Уведомление об ошибке отправлено в чат {message}')
            if errors:
                errors = False
                send_message(bot, message)
            time.sleep(RETRY_TIME)
            current_timestamp = int(time.time() - RETRY_TIME)
            continue


if __name__ == '__main__':
    main()
