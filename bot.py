from telebot import TeleBot
from telebot.types import InlineKeyboardMarkup, InlineKeyboardButton
from logic import *
import schedule
import threading
import time
from config import *

import cv2
import numpy as np
import os
from math import sqrt, ceil, floor


bot = TeleBot(API_TOKEN)


def gen_markup(id):
    markup = InlineKeyboardMarkup()
    markup.row_width = 1
    markup.add(InlineKeyboardButton("Получить!", callback_data=id))
    return markup

def create_collage(image_paths):
    images = []

    for path in image_paths:
        image = cv2.imread(path)

        if image is not None:
            images.append(image)

    if not images:
        return None

    num_images = len(images)

    num_cols = floor(sqrt(num_images))
    num_rows = ceil(num_images / num_cols)

    height, width = images[0].shape[:2]

    collage = np.zeros(
        (num_rows * height, num_cols * width, 3),
        dtype=np.uint8
    )

    for i, image in enumerate(images):
        image = cv2.resize(image, (width, height))

        row = i // num_cols
        col = i % num_cols

        collage[
            row * height:(row + 1) * height,
            col * width:(col + 1) * width
        ] = image

    return collage

@bot.callback_query_handler(func=lambda call: True)
def callback_query(call):

    prize_id = call.data
    user_id = call.message.chat.id

    if manager.get_winners_count(prize_id) < 3: # количество
        res = manager.add_winner(user_id, prize_id) # добавить победителей

        if res:
            img = manager.get_prize_img(prize_id)

            with open(f'img/{img}', 'rb') as photo:
                bot.send_photo(
                    user_id,
                    photo,
                    caption="Поздравляем! Ты получил картинку!"
                )
        else:
            bot.send_message(user_id, 'Ты уже получил картинку!')

    else:
        bot.send_message(
            user_id,
            "К сожалению, ты не успел получить картинку! Попробуй в следующий раз!"
        )

def send_message():
    prize_id, img = manager.get_random_prize()[:2]
    manager.mark_prize_used(prize_id)
    hide_img(img)

    for user in manager.get_users():
        with open(f'hidden_img/{img}', 'rb') as photo:
            bot.send_photo(
                user,
                photo,
                reply_markup=gen_markup(id=prize_id)
            )


def shedule_thread():
    schedule.every().minute.do(send_message)

    while True:
        schedule.run_pending()
        time.sleep(1)


@bot.message_handler(commands=['start'])
def handle_start(message):
    user_id = message.chat.id

    if user_id in manager.get_users():
        bot.reply_to(message, "Ты уже зарегестрирован!")
    else:
        manager.add_user(user_id, message.from_user.username)

        bot.reply_to(message, """Привет! Добро пожаловать! 
Тебя успешно зарегистрировали!
Каждый час тебе будут приходить новые картинки и у тебя будет шанс их получить!
Для этого нужно быстрее всех нажать на кнопку 'Получить!'

Только три первых пользователя получат картинку!""")


@bot.message_handler(commands=['get_my_score'])
def get_my_score(message):
    user_id = message.chat.id

    # Получаем картинки
    info = manager.get_winners_img(user_id)

    if not info:
        bot.send_message(
            user_id,
            "У тебя пока нет полученных картинок!"
        )
        return

    # Получаем названия выигранных картинок
    prizes = [x[0] for x in info]

    # Получаем все картинки
    image_paths = os.listdir('img')

    # Выигранные картинки берём из img/,
    # остальные — из hidden_img/
    image_paths = [
        f'img/{x}' if x in prizes else f'hidden_img/{x}'
        for x in image_paths
    ]

    # Создаём коллаж
    collage = create_collage(image_paths)

    if collage is None:
        bot.send_message(
            user_id,
            "Не удалось создать коллаж."
        )
        return

    # Сохраняем коллаж
    collage_path = f'collage_{user_id}.jpg'
    cv2.imwrite(collage_path, collage)

    # Отправляем коллаж пользователю
    with open(collage_path, 'rb') as photo:
        bot.send_photo(
            user_id,
            photo,
            caption="Вот твой текущий результат! 🏆"
        )

    # Удаляем временный файл
    os.remove(collage_path)

def polling_thread():
    bot.polling(none_stop=True)


if __name__ == '__main__':
    manager = DatabaseManager(DATABASE)
    manager.create_tables()

    polling_thread = threading.Thread(target=polling_thread)
    polling_shedule = threading.Thread(target=shedule_thread)

    polling_thread.start()
    polling_shedule.start()
