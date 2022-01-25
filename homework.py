import json
import logging
import os
import requests
import time
import telegram

from dotenv import load_dotenv
from http import HTTPStatus


load_dotenv()

PRACTICUM_TOKEN = os.getenv('PRACTICUM_TOKEN')
TELEGRAM_TOKEN = os.getenv('TELEGRAM_TOKEN')
TELEGRAM_CHAT_ID = os.getenv('TELEGRAM_CHAT_ID')

RETRY_TIME = 600
ENDPOINT = 'https://practicum.yandex.ru/api/user_api/homework_statuses/'
HEADERS = {'Authorization': f'OAuth {PRACTICUM_TOKEN}'}

HOMEWORK_STATUSES = {
    'approved': 'Работа проверена: ревьюеру всё понравилось. Ура!',
    'reviewing': 'Работа взята на проверку ревьюером.',
    'rejected': 'Работа проверена: у ревьюера есть замечания.'
}

logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)
handler = logging.StreamHandler()
logger.addHandler(handler)
formatter = logging.Formatter(
    '%(asctime)s - %(levelname)s - %(message)s'
)
handler.setFormatter(formatter)


def send_message(bot, message):
    """Отправляет сообщение в Telegram чат."""
    try:
        bot.send_message(TELEGRAM_CHAT_ID, message)
        logger.info('Удачная отправка сообщения в Telegram')
    except Exception:
        logger.error('Сбой при отправке сообщения в Telegram')


def get_api_answer(current_timestamp):
    """Делает запрос к единственному эндпоинту API-сервиса."""
    timestamp = current_timestamp or int(time.time())
    params = {'from_date': timestamp}
    try:
        response = requests.get(ENDPOINT, headers=HEADERS, params=params)
    except requests.exceptions.HTTPError as errh:
        logger.error(f'Http-ошибка:{errh}')
    except requests.exceptions.ConnectionError as errc:
        logger.error(f'Ошибка подключения:{errc}')
    except requests.exceptions.Timeout as errt:
        logger.error(f'Истекло время запроса:{errt}')
    except requests.exceptions.RequestException as err:
        logger.error(f'Другая ошибка запроса:{err}')
    if response.status_code != HTTPStatus.OK:
        logger.error('Недоступность эндпоинта')
        raise requests.exceptions.RequestException
    try:
        return response.json()
    except json.decoder.JSONDecodeError:
        logger.error('Ошибка преобразования в json')


def check_response(response):
    """Проверяет ответ API на корректность."""
    if type(response) is dict:
        if 'homeworks' in response:
            if len(
                response.get('homeworks')
            ) != 0 and type(
                response.get('homeworks')
            ) == list:
                return response.get('homeworks')
            else:
                raise Exception('Неккоректные данные в homeworks')
        else:
            logger.error('Отсутствие ожидаемых ключей в ответе API')
            raise KeyError('В словаре нет ключа homeworks')
    else:
        raise TypeError('Ответ API не является словарём')


def parse_status(homework):
    """Извлекает из информации о конкретной домашней работе статус."""
    homework_name = homework.get('homework_name')
    homework_status = homework.get('status')
    if homework_status in HOMEWORK_STATUSES:
        verdict = HOMEWORK_STATUSES[homework_status]
    else:
        logger.error('Недокументированный статус домашней работы')
        raise KeyError('Неизвестный статус')
    return f'Изменился статус проверки работы "{homework_name}". {verdict}'


def check_tokens():
    """Проверяет доступность переменных окружения."""
    if PRACTICUM_TOKEN and TELEGRAM_TOKEN and TELEGRAM_CHAT_ID:
        return True
    else:
        logger.critical('Отсутствие обязательных переменных'
                        + 'окружения во время запуска бота')
        return False


def main():
    """Основная логика работы бота."""
    if not check_tokens():
        raise Exception('Ошибка импорта токенов')
    bot = telegram.Bot(token=TELEGRAM_TOKEN)
    current_timestamp = int(time.time())
    while True:
        try:
            response = get_api_answer(current_timestamp)
            response = check_response(response)
            if len(response) > 0:
                homework = parse_status(response[0])
                if homework is not None:
                    send_message(bot, homework)
            else:
                logger.debug('Нет новых статусов')
            current_timestamp = response['current_date']
            time.sleep(RETRY_TIME)
        except Exception as error:
            message = f'Сбой в работе программы: {error}'
            send_message(bot, message)
            time.sleep(RETRY_TIME)


if __name__ == '__main__':
    main()
