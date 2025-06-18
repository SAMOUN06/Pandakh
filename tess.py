import sqlite3
from PIL import Image
from telebot import TeleBot
from io import BytesIO
import threading
import time
import logging
import requests
from telebot import TeleBot, types
from telebot.types import InlineKeyboardMarkup, InlineKeyboardButton
from datetime import datetime
from telebot.types import ReplyKeyboardMarkup, KeyboardButton
import os
import qrcode
from bakong_khqr import KHQR

# Set up logging
logging.basicConfig(level=logging.INFO)

# Telegram Bot Token
bot_token = "7794637327:AAHzdPW6Uqc5MVZSxK_FS372zZrSkjkW5XY"  # Replace with your actual bot token
bot = TeleBot(bot_token)

# API Token Bakong
api_token_bakong = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJkYXRhIjp7ImlkIjoiNmFmM2FlMWU3Yzg4NDQ3OCJ9LCJpYXQiOjE3NDM1MTE4MjUsImV4cCI6MTc1MTI4NzgyNX0.ShQ-iQ96VKcqktZZnigUgqaDuooeuPGpnduzdtNxBGA"
khqr = KHQR(api_token_bakong)

user_last_interaction = {}
user_states = {}

def handle_rate_limit(user_id):
    if user_id in user_last_interaction and time.time() - user_last_interaction[user_id] < 2:
        return False
    user_last_interaction[user_id] = time.time()
    return True

# List of admin user IDs
ADMIN_IDS = [1962908375]

# Item prices (key: item_id, value: price in $)
ITEM_PRICES = {
    "11": {"normal": 0.25, "reseller": 0.22},
    "22": {"normal": 0.50, "reseller": 0.44},
    "86": {"normal": 1.25, "reseller": 1.15},
    "172": {"normal": 2.45, "reseller": 2.25},
    "257": {"normal": 3.50, "reseller": 3.20},
    "343": {"normal": 4.63, "reseller": 3.33},
    "429": {"normal": 5.70, "reseller": 5.43},
    "514": {"normal": 6.80, "reseller": 6.42},
    "600": {"normal": 7.90, "reseller": 7.53},
    "706": {"normal": 9.10, "reseller": 8.61},
    "792": {"normal": 9.95, "reseller": 9.65},
    "878": {"normal": 12.10, "reseller": 10.38},
    "963": {"normal": 12.10, "reseller": 11.55},
    "1050": {"normal": 13.40, "reseller": 12.80},
    "1135": {"normal": 14.42, "reseller": 13.75},
    "1412": {"normal": 17.80, "reseller": 16.75},
    "1584": {"normal": 19.99, "reseller": 18.99},
    "1755": {"normal": 23.28, "reseller": 21.28},
    "1926": {"normal": 24.89, "reseller": 22.89},
    "2195": {"normal": 27.37, "reseller": 25.32},
    "2538": {"normal": 31.60, "reseller": 29.35},
    "2901": {"normal": 35.72, "reseller": 33.55},
    "4394": {"normal": 52.80, "reseller": 50.60},
    "5532": {"normal": 65.80, "reseller": 63.60},
    "6238": {"normal": 77.15, "reseller": 71.90},
    "6944": {"normal": 85.50, "reseller": 79.83},
    "8433": {"normal": 0.0, "reseller": 0.0},
    "9288": {"normal": 116.00, "reseller": 113.00},
    "Weekly": {"normal": 1.40, "reseller": 1.37},
    "2Weekly": {"normal": 2.80, "reseller": 2.70},
    "3Weekly": {"normal": 4.20, "reseller": 4.10},
    "4Weekly": {"normal": 5.60, "reseller": 5.40},
    "5Weekly": {"normal": 7.00, "reseller": 6.20},
    "Twilight": {"normal": 7.35, "reseller": 6.85},
    "50x2": {"normal": 0.90, "reseller": 0.80},
    "150x2": {"normal": 2.40, "reseller": 2.20},
    "250x2": {"normal": 3.85, "reseller": 3.55},
    "500x2": {"normal": 7.19, "reseller": 6.90},
}

ITEM_FF_PRICES = {
    "25": {"normal": 0.28, "reseller": 0.25},
    "100": {"normal": 0.90, "reseller": 0.85},
    "310": {"normal": 2.65, "reseller": 2.55},
    "520": {"normal": 4.25, "reseller": 4.10},
    "1060": {"normal": 8.65, "reseller": 8.25},
    "2180": {"normal": 16.50, "reseller": 16.15},
    "5600": {"normal": 43.00, "reseller": 41.00},
    "11500": {"normal": 85.00, "reseller": 82.00},
    "Weekly": {"normal": 1.50, "reseller": 1.45},
    "WeeklyLite": {"normal": 0.40, "reseller": 0.35},
    "Monthly": {"normal": 7.00, "reseller": 6.72},
    "Evo3D": {"normal": 0.60, "reseller": 0.56},
    "Evo7D": {"normal": 0.90, "reseller": 0.82},
    "Evo30D": {"normal": 2.45, "reseller": 2.33},
    "Levelpass": {"normal": 3.45, "reseller": 3.30},
}

# Database setup
def init_db():
    conn = sqlite3.connect('user_balances.db')
    cursor = conn.cursor()
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS balances (
            user_id INTEGER PRIMARY KEY,
            balance REAL NOT NULL DEFAULT 0,
            is_reseller INTEGER DEFAULT 0
        )
    ''')
    conn.commit()
    conn.close()

# Function to get user balance
def get_user_balance(user_id):
    conn = sqlite3.connect('user_balances.db')
    cursor = conn.cursor()
    cursor.execute('SELECT balance FROM balances WHERE user_id = ?', (user_id,))
    result = cursor.fetchone()
    conn.close()
    return result[0] if result else 0

# Function to update user balance
def update_user_balance(user_id, amount):
    current_balance = get_user_balance(user_id)
    new_balance = current_balance + amount
    conn = sqlite3.connect('user_balances.db')
    cursor = conn.cursor()
    cursor.execute('INSERT OR REPLACE INTO balances (user_id, balance) VALUES (?, ?)', (user_id, new_balance))
    conn.commit()
    conn.close()

# Check if a user is a reseller
def is_reseller(user_id):
    try:
        conn = sqlite3.connect("user_balances.db")
        cursor = conn.cursor()
        cursor.execute("SELECT is_reseller FROM balances WHERE user_id = ?", (user_id,))
        result = cursor.fetchone()
        conn.close()
        return result[0] == 1 if result else False
    except Exception as e:
        logging.error(f"Error checking reseller status for user {user_id}: {e}")
        return False       

# Set a user as a reseller
def add_reseller(user_id):
    conn = sqlite3.connect("user_balances.db")
    cursor = conn.cursor()
    cursor.execute("INSERT OR IGNORE INTO balances (user_id) VALUES (?)", (user_id,))
    cursor.execute("UPDATE balances SET is_reseller = 1 WHERE user_id = ?", (user_id,))
    conn.commit()
    conn.close()

# Unset a user as a reseller
def remove_reseller(user_id):
    conn = sqlite3.connect("user_balances.db")
    cursor = conn.cursor()
    cursor.execute("INSERT OR IGNORE INTO balances (user_id) VALUES (?)", (user_id,))
    cursor.execute("UPDATE balances SET is_reseller = 0 WHERE user_id = ?", (user_id,))
    conn.commit()
    conn.close()        

# Command to set a user as a reseller
@bot.message_handler(commands=['addre'])
def add_reseller_handler(message):
    admin_id = message.from_user.id
    if admin_id not in ADMIN_IDS:
        bot.reply_to(message, "You are not authorized to use this command.")
        return

    try:
        target_user_id = int(message.text.split()[1])
        add_reseller(target_user_id)
        bot.reply_to(message, f"✅ User {target_user_id} is now a reseller.")
    except (IndexError, ValueError):
        bot.reply_to(message, "Usage: /addre <user_id>")

# Command to unset a user as a reseller
@bot.message_handler(commands=['delre'])
def remove_reseller_handler(message):
    admin_id = message.from_user.id
    if admin_id not in ADMIN_IDS:
        bot.reply_to(message, "You are not authorized to use this command.")
        return

    try:
        target_user_id = int(message.text.split()[1])
        remove_reseller(target_user_id)
        bot.reply_to(message, f"✅ User {target_user_id} is no longer a reseller.")
    except (IndexError, ValueError):
        bot.reply_to(message, "Usage: /delre <user_id>")

# Command to set item prices
def set_price_handler(message, item_prices):
    admin_id = message.from_user.id
    if admin_id not in ADMIN_IDS:
        bot.reply_to(message, "You are not authorized to use this command.")
        return

    try:
        args = message.text.split()
        if len(args) != 4:
            bot.reply_to(message, "Usage: /set_price <item_id> <normal_price> <reseller_price>")
            return

        item_id = args[1]
        normal_price = float(args[2])
        reseller_price = float(args[3])

        if item_id in item_prices:
            item_prices[item_id]["normal"] = normal_price
            item_prices[item_id]["reseller"] = reseller_price
            bot.reply_to(message, f"✅ Prices updated for item {item_id}:\nNormal Price: ${normal_price}\nReseller Price: ${reseller_price}")
        else:
            bot.reply_to(message, f"Item ID {item_id} does not exist.")

    except (IndexError, ValueError):
        bot.reply_to(message, "Invalid input. Please ensure you provide valid prices.")

@bot.message_handler(commands=['set_ml'])
def set_ml_handler(message):
    set_price_handler(message, ITEM_PRICES)

@bot.message_handler(commands=['set_ff'])
def set_ff_handler(message):
    set_price_handler(message, ITEM_FF_PRICES)

@bot.message_handler(commands=['allbal'])
def allbal_handler(message):
    admin_id = message.from_user.id
    if admin_id not in ADMIN_IDS:
        bot.reply_to(message, "You are not authorized to use this command.")
        return

    conn = sqlite3.connect('user_balances.db')
    cursor = conn.cursor()
    cursor.execute('SELECT user_id, balance FROM balances')
    results = cursor.fetchall()
    conn.close()

    file_content = "User ID, Balance\n"
    for user_id, balance in results:
        file_content += f"{user_id}, {balance:.2f}\n"

    file_path = "user_balances.txt"
    with open(file_path, "w") as file:
        file.write(file_content)

    with open(file_path, "rb") as file:
        bot.send_document(admin_id, file, caption="ទិន្នន័យ")

    os.remove(file_path)

# Command to add balance to a user
@bot.message_handler(commands=['addb'])
def addb_handler(message):
    admin_id = message.from_user.id
    if admin_id not in ADMIN_IDS:
        bot.reply_to(message, "You are not authorized to use this command.")
        return

    try:
        args = message.text.split()
        if len(args) != 3:
            bot.reply_to(message, "Usage: /addb <user_id> <amount>")
            return

        target_user_id = int(args[1])
        amount = float(args[2])

        if amount <= 0:
            bot.reply_to(message, "Amount must be greater than 0.")
            return

        update_user_balance(target_user_id, amount)
        bot.reply_to(message, f"✅ Added ${amount:.2f} to user {target_user_id}'s balance.")
    except (IndexError, ValueError):
        bot.reply_to(message, "Invalid input. Please ensure you provide a valid user ID and amount.")

# Initialize the database
init_db()

@bot.message_handler(commands=['start'])
def send_welcome(message):
    nickname = message.from_user.first_name or "អ្នកប្រើប្រាស់"
    welcome_message = (
        f"✅ សូមស្វាគមន៍ {nickname} ដែលបានមកកាន់ bot របស់យើងខ្ញុំ 🙏✨\n\n"
        "👉 សុវត្ថិភាពជូនអតិថិជន\n"
        "👉 តម្លៃសមរម្យ\n"
        "👉 មិនមានការបែនអាខោន\n"
        "👉 ដាក់បានលឿនរហ័សទាន់ចិត្ដ\n\n"
        "➡️Channel: @kenzy_gaming\n"
        "➡️Owner: @KENZY_STORE72\n\n"
        "➡️ប្រតិបត្តិការ: @KenzyTopup247\n\n"
    )
    
    markup = ReplyKeyboardMarkup(row_width=4, resize_keyboard=True)
    button1 = KeyboardButton('👤 គណនី')
    button2 = KeyboardButton('🎮 Game')
    button3 = KeyboardButton('💰 ដាក់ប្រាក់')
    button4 = KeyboardButton('♻️ របៀបទិញ')
    markup.add(button1, button2, button3)
    markup.add(button4)
    
    with open("logo.jpg", "rb") as photo:
        bot.send_photo(message.chat.id, photo, caption=welcome_message, reply_markup=markup)

@bot.message_handler(func=lambda message: message.text == '👤 គណនី')
def handle_account(message):
    chat_id = message.chat.id
    user_id = message.from_user.id
    username = message.from_user.username or "Unknown"
    user_balance = get_user_balance(chat_id)
    bot.send_message(chat_id, f"Name: {username}\nID: {user_id}\nBalance: ${user_balance:.2f} USD")

@bot.message_handler(func=lambda message: message.text == '🎮 Game')
def handle_game(message):
    markup = ReplyKeyboardMarkup(row_width=2, resize_keyboard=True)
    button1 = KeyboardButton('Mobile Legends')
    button2 = KeyboardButton('Free Fire')
    button_back = KeyboardButton('🔙 Back')  # Unified Back button
    markup.add(button1, button2, button_back)
    bot.send_message(message.chat.id, "Select product category", reply_markup=markup)

@bot.message_handler(func=lambda message: message.text == '🔙 Back')
def handle_back(message):
    user_id = message.from_user.id
    if not handle_rate_limit(user_id):
        bot.send_message(message.chat.id, "Please wait a moment before trying again.")
        return
    if user_id in user_states:
        del user_states[user_id]  # Clear any deposit state
    send_welcome(message)

@bot.message_handler(func=lambda message: message.text == 'Mobile Legends')
def handle_game_choice(message):
    user_id = message.from_user.id
    if is_reseller(user_id):
        product_list = "\n".join([f"{item_id} - {data['reseller']:.2f}" for item_id, data in ITEM_PRICES.items()])
        bot.send_message(message.chat.id, f"""Products List Mobile Legends (Reseller)\n\n{product_list}\n\nExample format order:
 123456789 12345 Weekly
 userid serverid item""")
    else:
        product_list1 = "\n".join([f"{item_id} - ${data['normal']:.2f}" for item_id, data in ITEM_PRICES.items()])
        bot.send_message(message.chat.id, f"""Products List Mobile Legends\n\n{product_list1}\n\nExample format order:
 123456789 12345 Weekly
 userid serverid item""")

@bot.message_handler(func=lambda message: message.text == 'Free Fire')
def handle_free_fire(message):
    user_id = message.from_user.id
    if is_reseller(user_id):
        product_list2 = "\n".join([f"{item_id} - {data['reseller']:.2f}" for item_id, data in ITEM_FF_PRICES.items()])
        bot.send_message(message.chat.id, f"""Products List Free Fire (Reseller)\n\n{product_list2}\n\nExample format order:
 123456789 0 Weekly
 userid serverid item""")
    else:
        product_list3 = "\n".join([f"{item_id} - ${data['normal']:.2f}" for item_id, data in ITEM_FF_PRICES.items()])
        bot.send_message(message.chat.id, f"""Products List Free Fire\n\n{product_list3}\n\nExample format order:
 123456789 0 Weekly
 userid serverid item""")

@bot.message_handler(func=lambda message: message.text == "💰 ដាក់ប្រាក់")
def deposit_handler(message):
    user_id = message.chat.id
    bot.send_message(user_id, " សូមបញ្ចូលចំនួនប្រាក់ដែលអ្នកចង់បង់ ជាលុយ$ ex: 0.01 ឬ 1")
    bot.register_next_step_handler(message, get_amount)

def get_amount(message):
    user_id = message.chat.id
    amount_text = message.text.strip()

    try:
        amount = float(amount_text)
        if amount <= 0:
            raise ValueError("Amount must be greater than 0.")

        qr_data = khqr.create_qr(
            bank_account='samoun_mov1@wing',
            merchant_name='PANDA KH',
            merchant_city='Phnom Penh',
            amount=amount,
            currency='USD',
            store_label='MShop',
            phone_number='855 97 slashing 8047985',
            bill_number='TRX019283775',
            terminal_label='Cashier-01',
            static=False
        )

        md5_item = khqr.generate_md5(qr_data)
        qr_image = qrcode.make(qr_data)
        qr_image_io = BytesIO()
        qr_image.save(qr_image_io, 'PNG')
        qr_image_io.seek(0)

        caption = (
            "Here is your payment 𝐐𝐑 code\n"
            "Note: Expires in 3 minutes."
        )

        markup = ReplyKeyboardMarkup(resize_keyboard=True, one_time_keyboard=True)
        check_button = KeyboardButton("✅ពិនិត្យការទូទាត់")
        back_button = KeyboardButton("🔙 Back")  # Unified Back button
        markup.add(check_button, back_button)

        sent_qr_message = bot.send_photo(user_id, qr_image_io, caption=caption)
        bot.send_message(
            user_id,
            "✅ សូមចុច 'ពិនិត្យការទូទាត់' ដើម្បីពិនិត្យការបង់ប្រាក់។\n⚠️ បញ្ជាក់សូមកុំផ្ញើ វិក័យប័ត្រ មកកាន់ខ្ញុំវិញ!",
            reply_markup=markup
        )

        bot.register_next_step_handler_by_chat_id(user_id, lambda m: check_payment(m, md5_item, sent_qr_message, amount))

    except ValueError:
        bot.send_message(user_id, "❌ចំនួនមិនត្រឹមត្រូវ សូមបញ្ចូលចំនួនត្រឹមត្រូវដែលធំជាង 0.01")
    except Exception as e:
        bot.send_message(user_id, f"Error generating QR Code: {str(e)}")

def check_payment_automated(user_id, md5_item, sent_qr_message, amount):
    try:
        result_transaction = khqr.check_payment(md5_item)

        if result_transaction == "PAID":
            update_user_balance(user_id, amount)

            current_time = datetime.now().strftime("%d/%m/%Y %H:%M")
            username = bot.get_chat(user_id).username or "Unknown"

            success_message = (
                "Automated Deposit System ⚙️\n\n"
                f"Currency : USD 💵\n\n"
                f"Balance Added :\n"
                f"${amount:.2f} ✅\n\n"
                f"Time Now :\n"
                f"{current_time} ⏰\n\n"
                f"Payment :\n"
                f"KHQR PAYMENT SCAN\n\n"
                f"Telegram : @{username}\n"
                f"Telegram ID : {user_id}"          
            )

            bot.send_message(user_id, success_message)
            bot.delete_message(user_id, sent_qr_message.message_id)
            return True

        elif result_transaction == "UNPAID":
            return False

        else:
            bot.send_message(user_id, f"Unexpected response: {result_transaction}")
            return False

    except Exception as e:
        bot.send_message(user_id, f"Error checking payment: {str(e)}")
        return False

def check_payment(message, md5_item, sent_qr_message, amount):
    user_id = message.chat.id

    for _ in range(30):
        time.sleep(1)
        if check_payment_automated(user_id, md5_item, sent_qr_message, amount):
            break
    else:
        bot.send_message(user_id, "❌ ការទូទាត់មិនសម្រេច។ សូមព្យាយាមម្តងទៀត។")

@bot.message_handler(func=lambda message: message.text.replace('.', '', 1).isdigit())
def amount_handler(message):
    amount = message.text
    user_id = message.from_user.id
    username = message.from_user.username or "អ្នកប្រើប្រាស់"
    
    user_states[user_id] = {"amount": amount}
    
    with open("qr.jpg", "rb") as photo:
        bot.send_photo(message.chat.id, photo, caption=f"⏳ ផុតកំណត់ក្នុងរយៈពេល 3 នាទី!\n\n📩 ផ្ញើវិក័យប័ត្រមកកាន់ខ្ញុំ")
    
    if user_id in user_states:
        user_states[user_id]["photo_id"] = message.photo[-1].file_id if message.photo else None
        bot.send_message(message.chat.id, "✅ រូបភាពត្រូវបានទទួល។ សូមចុចប៊ូតុង '✔️ យល់ព្រម' ដើម្បីបញ្ជូនទិន្នន័យទៅ admin។")
    else:
        bot.send_message(message.chat.id, "❌ មិនមានទិន្នន័យដាក់ប្រាក់។ សូមព្យាយាមម្តងទៀត។")

@bot.message_handler(func=lambda message: message.text == "✔️ យល់ព្រម")
def confirm_handler(message):
    user_id = message.from_user.id
    username = message.from_user.username or "អ្នកប្រើប្រាស់"
    
    if user_id in user_states and "amount" in user_states[user_id] and "photo_id" in user_states[user_id]:
        amount = user_states[user_id]["amount"]
        photo_id = user_states[user_id]["photo_id"]
        
        markup = InlineKeyboardMarkup()
        wrong_button = InlineKeyboardButton("❌ ខុស", callback_data=f"wrong_{user_id}_{amount}")
        correct_button = InlineKeyboardButton("✔️ ត្រូវ", callback_data=f"correct_{user_id}_{amount}")
        markup.add(wrong_button, correct_button)
        
        for admin_id in ADMIN_IDS:
            bot.send_photo(admin_id, photo_id, caption=f"📩 ការដាក់ប្រាក់ថ្មី\n\n👤 អ្នកប្រើប្រាស់: @{username}\n🆔 User ID: {user_id}\n💰 ចំនួនទឹកប្រាក់: {amount}$", reply_markup=markup)
        
        send_welcome(message)
        del user_states[user_id]
    else:
        bot.send_message(message.chat.id, "❌ មិនមានទិន្នន័យដាក់ប្រាក់ឬរូបភាព។ សូមព្យាយាមម្តងទៀត។")

@bot.callback_query_handler(func=lambda call: True)
def callback_handler(call):
    data = call.data.split("_")
    action = data[0]
    target_user_id = int(data[1])
    amount = float(data[2])
    
    if action == "wrong":
        bot.answer_callback_query(call.id, "❌ ការដាក់ប្រាក់នេះខុស។")
        bot.send_message(target_user_id, f"❌ ការដាក់ប្រាក់ទទួលបានបរាជ័យ។")
    
    elif action == "correct":
        bot.answer_callback_query(call.id, "✅ ការដាក់ប្រាក់នេះត្រឹមត្រូវ។")
        update_user_balance(target_user_id, amount)
        bot.send_message(target_user_id, f"🎉🎊 ការដាក់ប្រាក់ទទួលបានជោគជ័យ: ${amount:.2f}។")
    
    bot.delete_message(call.message.chat.id, call.message.message_id)

@bot.message_handler(content_types=['photo'])
def photo_handler(message):
    user_id = message.from_user.id
    username = message.from_user.username or "អ្នកប្រើប្រាស់"
    
    if user_id in user_states:
        amount = user_states[user_id]["amount"]
        photo_id = message.photo[-1].file_id
        
        for admin_id in ADMIN_IDS:
            bot.send_photo(admin_id, photo_id, caption=f"📩 ការដាក់ប្រាក់ថ្មី\n\n👤 អ្នកប្រើប្រាស់: @{username}\n🆔 User ID: {user_id}\n💰 ចំនួនទឹកប្រាក់: {amount}$")
        
        send_welcome(message)
    else:
        bot.send_message(message.chat.id, "❌ មិនមានទិន្នន័យដាក់ប្រាក់។ សូមព្យាយាមម្តងទៀត។")

@bot.message_handler(func=lambda message: len(message.text.split()) == 3)
def buy_item_handler(message):
    try:
        user_id = message.from_user.id
        args = message.text.split()

        try:
            server_id = int(args[0])
            zone_id = int(args[1])
            item_id = args[2]
        except ValueError:
            bot.send_message(message.chat.id, "Invalid server ID or zone ID. Please enter valid numbers.")
            return

        price_list = ITEM_FF_PRICES if zone_id == 0 else ITEM_PRICES

        if item_id not in price_list:
            bot.send_message(message.chat.id, f"Item ID {item_id} does not exist.")
            return

        price = price_list[item_id]["reseller"] if is_reseller(user_id) else price_list[item_id]["normal"]

        balance = get_user_balance(user_id)
        if balance < price:
            bot.send_message(message.chat.id, f"Insufficient balance. The item costs ${price:.2f}. Please add funds.")
            return

        nickname = "Unknown"
        if zone_id != 0:
            api_url = f"https://api.isan.eu.org/nickname/ml?id={server_id}&zone={zone_id}"
            try:
                response = requests.get(api_url)
                response.raise_for_status()
                data = response.json()
                if data.get("success"):
                    nickname = data.get("name", "unfinded")
                else:
                    bot.reply_to(message, "Wrong ID")
                    return
            except requests.RequestException as e:
                bot.send_message(message.chat.id, "Error validating ID MLBB. Please try again later.")
                logging.error(f"API request failed: {e}")
                return

        update_user_balance(user_id, -price)

        bot.send_message(message.chat.id, f"New Order Successfully ❇️\nPlayer ID: {server_id}\nServer ID: {zone_id}\nNickname: {nickname}\nProduct: {item_id}\nStatus: Success ✅")

        group_ff_id = -1002708405356
        group_mlbb_id = -1002708405356
        group_operations_id = -1002708405356

        purchase_details = f"{server_id} {zone_id} {item_id}"
        if zone_id == 0:
            send_group_message(group_ff_id, purchase_details)
        else:
            send_group_message(group_mlbb_id, purchase_details)

        buyer_info = f"New Order Successfully ❇️\nGame: {'Free Fire' if zone_id == 0 else 'Mobile Legends'}\nPlayer ID: {server_id}\nServer ID: {zone_id}\nNickname: {nickname}\nProduct: {item_id}\nStatus: Success ✅"
        send_group_message(group_operations_id, buyer_info)

    except Exception as e:
        bot.send_message(message.chat.id, f"An error occurred: {e}")
        logging.error(f"Error in buy_item_handler: {e}")

def send_group_message(group_id, message):
    try:
        bot.send_message(group_id, message)
    except Exception as e:
        logging.error(f"Failed to send message to group {group_id}: {e}")

if __name__ == "__main__":
    init_db()
    logging.info("Bot is running...")
    bot.infinity_polling()