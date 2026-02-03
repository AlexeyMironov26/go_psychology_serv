import json
import sqlite3 # норма враждебности 3.5-10
import logging # норма агрессивности 17-25
import os
from datetime import datetime
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    Application, CommandHandler, CallbackQueryHandler, 
    ContextTypes, MessageHandler, filters
)
from admin_handlers import AdminHandler

# Настройка логирования
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.DEBUG
)
logger = logging.getLogger(__name__)

class PsychBot:
    def __init__(self, token: str):
        self.token = token
        self.admin_handler = AdminHandler()
        self.questions = self.get_test_questions()
        
    def init(self):
        workers = (os.cpu_count() or 4) + 2
        self.application = Application.builder()\
            .token(self.token)\
            .concurrent_updates(True)\
            .build()
        
        self.init_database()
        self.setup_handlers()
        # self.load_last_update_id()
    
    def init_database(self):
        """Инициализация базы данных SQLite с таймаутом"""
        try:
            conn = sqlite3.connect('psych_bot.db', timeout=10)
            cursor = conn.cursor()
            
            # Таблица для последнего update_id
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS updates (
                    id INTEGER PRIMARY KEY,
                    last_update_id INTEGER
                )
            ''')
            
            # Таблица пользователей
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS users (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    telegram_id INTEGER UNIQUE,
                    full_name TEXT,
                    user_group TEXT,
                    faculty TEXT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            ''')
            
            # Таблица результатов теста на агрессию
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS aggression_test_results (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id INTEGER,
                    test_name TEXT DEFAULT 'Опросник исследования уровня агрессивности',
                    physical_aggression INTEGER,
                    indirect_aggression INTEGER,
                    irritation INTEGER,
                    negativism INTEGER,
                    resentment INTEGER,
                    suspicion INTEGER,
                    verbal_aggression INTEGER,
                    guilt INTEGER,
                    aggression_index INTEGER,
                    hostility_index INTEGER,
                    completed_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (user_id) REFERENCES users (id)
                )
            ''')
            
            conn.commit()
            conn.close()
            logger.info("Database initialized successfully")
            
        except sqlite3.OperationalError as e:
            logger.error(f"Database initialization error: {e}")
            raise
    
    def save_user(self, telegram_id, full_name, user_group, faculty):
        """Сохранение пользователя в БД"""
        try:
            conn = sqlite3.connect('psych_bot.db', timeout=5)
            cursor = conn.cursor()
            
            # Сначала проверяем, есть ли пользователь
            cursor.execute('SELECT id FROM users WHERE telegram_id = ?', (telegram_id,))
            existing_user = cursor.fetchone()
            
            if existing_user:
                # Обновляем существующего пользователя
                cursor.execute('''
                    UPDATE users 
                    SET full_name = ?, user_group = ?, faculty = ?
                    WHERE telegram_id = ?
                ''', (full_name.lower(), user_group, faculty, telegram_id))
            else:
                # Добавляем нового пользователя
                cursor.execute('''
                    INSERT INTO users 
                    (telegram_id, full_name, user_group, faculty) 
                    VALUES (?, ?, ?, ?)
                ''', (telegram_id, full_name.lower(), user_group, faculty))
            
            conn.commit()
            conn.close()
            return True
        except sqlite3.OperationalError as e:
            logger.error(f"Error saving user: {e}")
            return False
        except Exception as e:
            logger.error(f"Unexpected error saving user: {e}")
            return False
        
    def save_test_result(self, telegram_id, scores):
        """Сохранение результата теста в БД"""
        try:
            conn = sqlite3.connect('psych_bot.db', timeout=5)
            cursor = conn.cursor()
            
            # Получаем user_id
            cursor.execute('SELECT id FROM users WHERE telegram_id = ?', (telegram_id,))
            user = cursor.fetchone()
            
            if not user:
                logger.error(f"User {telegram_id} not found in database")
                # Попробуем получить user_id по имени (на случай если telegram_id не совпал)
                cursor.execute('SELECT id FROM users ORDER BY id DESC LIMIT 1')
                user = cursor.fetchone()
                if not user:
                    logger.error("No users found in database at all")
                    return False
            
            user_id = user[0]
            
            # Сохраняем результаты
            cursor.execute('''
                INSERT INTO aggression_test_results 
                (user_id, physical_aggression, indirect_aggression, irritation,
                negativism, resentment, suspicion, verbal_aggression, guilt,
                aggression_index, hostility_index)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''', (
                user_id,
                scores['physical_aggression'],
                scores['indirect_aggression'],
                scores['irritation'],
                scores['negativism'],
                scores['resentment'],
                scores['suspicion'],
                scores['verbal_aggression'],
                scores['guilt'],
                scores['aggression_index'],
                scores['hostility_index']
            ))
            
            conn.commit()
            conn.close()
            logger.info(f"Test result saved for user_id: {user_id}")
            return True
            
        except sqlite3.OperationalError as e:
            logger.error(f"Error saving test result: {e}")
            return False
        except Exception as e:
            logger.error(f"Unexpected error saving test result: {e}")
            return False
    
    def setup_handlers(self):
        """Настройка обработчиков"""
        # Обработчики команд
        self.application.add_handler(CommandHandler("start", self.start))
        self.application.add_handler(CommandHandler("results", self.results))
        
        # Callback (обработчик нажатий на кнопки) обработчик
        self.application.add_handler(CallbackQueryHandler(self.handle_callback))
        
        # Обработчик сообщений
        self.application.add_handler(MessageHandler(
            filters.TEXT & ~filters.COMMAND, self.handle_message #первый параметр говорит, что обработчик будет ловить все 
            #текстовые сообщения (апдейты, являющиеся ими) кроме комманд
        ))
    
    async def start(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Обработка команды /start"""
        user = update.effective_user
        telegram_id = user.id
        
        # Проверка на администратора
        if self.admin_handler.is_admin(telegram_id):
            await self.admin_handler.admin_start(update, context)
            return
        
        # Для обычных пользователей - начинаем регистрацию
        context.user_data['registration_step'] = 'ask_name'
        
        await update.message.reply_text(
            "Добро пожаловать в психологическую службу МТУСИ!\n\n"
            "Перед прохождением тестирования необходимо заполнить данные.\n\n"
            "Введите ваше ФИО (например: Иванов Иван Иванович):"
        )
    
    async def results(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Обработка команды /results"""
        telegram_id = update.effective_user.id
        
        if not self.admin_handler.is_admin(telegram_id):
            await update.message.reply_text("Извините, вы не админ и поэтому вам отказано в доступе:/")
            return
        
        await self.admin_handler.admin_start(update, context)
    
    async def handle_callback(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Обработка callback запросов"""
        query = update.callback_query
        await query.answer()
        
        data = query.data
        logger.info(f"📞 CALLBACK RECEIVED: {data}")
        
        # Административные callback
        if (data.startswith("admin_") or 
        data.startswith("avg_") or 
        data.startswith("all_") or 
        data.startswith("raw_")) or data.startswith("fac_"):
            logger.info(f"→ Routing to admin handler")
            await self.handle_admin_callback(update, context)
        
        # Callback регистрации
        elif data.startswith("reg_"):
            logger.info(f"→ Routing to registration handler")
            await self.handle_registration_callback(query, context)
        
        # Callback тестирования И ответы на вопросы
        elif data.startswith("test_") or data.startswith("answer_"):
            logger.info(f"→ Routing to test handler")
            await self.handle_test_callback(query, context)
        
        else:
            logger.warning(f"⚠️ Unknown callback (my main handler): {data}")
    
    async def handle_admin_callback(self, update, context):
        """Обработка административных callback"""
        query = update.callback_query
        data = query.data
        logger.info(f"📞 ADMIN CALLBACK: {data}")
        
        try:
            if data == "admin_faculty_avg":
                await self.admin_handler.show_admin_tests_menu(query, "faculty_avg")
            
            elif data == "admin_all_avg":
                await self.admin_handler.show_admin_tests_menu(query, "all_avg")
            
            elif data == "admin_raw_results":
                await self.admin_handler.show_admin_tests_menu(query, "raw")
            
            # Обработка выбора теста для средних значений
            elif data == "avg_aggression":
                await self.admin_handler.show_faculty_selection(query, "aggression")
            
            elif data == "all_aggression":
                # Для всех факультетов передаем None вместо конкретного факультета
                await self.admin_handler.show_all_averages(query, "aggression")
            
            elif data == "raw_aggression":
                await self.admin_handler.show_raw_data_menu(update)
            
            # Обработка выбора факультета (новый формат: "fac_1_agg" или "fac_1_raw")
            elif data.startswith("fac_"):
                parts = data.split("_")
                logger.info(f"📊 Faculty callback parts: {parts}")
                
                if len(parts) >= 3:
                    faculty_code = parts[1]  # "1", "2", "3", "4" - КОД факультета
                    test_type = parts[2]     # "agg" или "raw"
                    
                    if test_type == "agg":
                        # Передаем КОД факультета в show_faculty_averages
                        # Метод сам преобразует код в название
                        await self.admin_handler.show_faculty_averages(query, faculty_code, test_type)
                    
                    elif test_type == "raw":
                        # Для сырых данных: получаем название по коду
                        faculty_name = self.admin_handler.code_to_faculty.get(faculty_code)
                        if faculty_name:
                            await self.admin_handler.show_raw_data(update, faculty=faculty_name)
                        else:
                            await query.message.reply_text("❌ Факультет не найден")
            
            # Обработка сырых данных меню
            elif data == "raw_single":
                # Для получения сырых данных одного человека
                logger.warning(f"⚠️ INSIDE RAW SINGLE CONDITION")
                context.user_data['awaiting_name'] = True
                await query.message.reply_text(
            "Введите, пожалуйста, ФИО интересующего студента (например: Иванов Иван Иванович):"
        )
            
            elif data == "raw_faculty":
                logger.warning(f"⚠️ INSIDE RAW FACULTY CONDITION")
                # Для сырых данных показываем выбор факультета
                await self.admin_handler.show_faculty_selection(query, "raw")
            
            elif data == "raw_all":
                logger.warning(f"⚠️ INSIDE RAW ALL FACULTY CONDITION")
                #для сырых данных всех факультетов
                await self.admin_handler.show_raw_data(update)
            
            else:
                logger.warning(f"⚠️ Unknown admin callback (by admin_handler): {data}")
                await query.message.reply_text("❌ Неизвестная команда")
        
        except Exception as e:
            logger.error(f"❌ Error in handle_admin_callback: {e}")
            await query.message.reply_text("❌ Произошла ошибка при обработке запроса")
    
    async def handle_registration_callback(self, query, context):
        """Обработка callback регистрации"""
        data = query.data
        
        # Обработка выбора факультета
        if data.startswith("reg_faculty_"):
            faculty_map = {
                "reg_faculty_radio": "Радио и Телевидение",
                "reg_faculty_it": "Информационные Технологии",
                "reg_faculty_networks": "Сети и Системы Связи",
                "reg_faculty_cyber": "Кибернетика и Информационная Безопасность",
                "reg_faculty_digEco": "Цифровая экономика и массовые коммуникации"
            }
            
            if data in faculty_map:
                context.user_data['faculty'] = faculty_map[data]
                await query.edit_message_text(
                    "Введите вашу учебную группу (например: БСТ2201):"
                )
                context.user_data['registration_step'] = 'ask_group'
        
        # Остальной код остается как был
        elif data == "reg_confirm":
            # Показываем инструкцию
            instruction = (
                "Предлагаем Вам ответить на ряд вопросов. "
                "Отвечайте только \"да\" или \"нет\", не раздумывая, сразу же, "
                "так как важна ваша первая реакция. "
                "Имейте в виду, что исследуются некоторые личностные, "
                "а не умственные особенности, так что правильных или "
                "неправильных ответов здесь нет."
            )
            
            keyboard = [[InlineKeyboardButton("Продолжить", callback_data="reg_continue")]]
            reply_markup = InlineKeyboardMarkup(keyboard)
            
            await query.edit_message_text(instruction, reply_markup=reply_markup)
        
        elif data == "reg_continue":
            # Показываем выбор теста
            keyboard = [[
                InlineKeyboardButton(
                    "Тест на исследование уровня агрессивности", 
                    callback_data="test_start_aggression"
                )
            ]]
            reply_markup = InlineKeyboardMarkup(keyboard)
            
            await query.edit_message_text(
                "Выберите тест, который озвучил преподаватель:",
                reply_markup=reply_markup
            )

    async def handle_test_callback(self, query, context):
        """Обработка callback тестирования"""
        data = query.data
        
        if data == "test_start_aggression":
            # Начинаем тест
            context.user_data['test_answers'] = []
            context.user_data['current_question'] = 0
            context.user_data['test_type'] = 'aggression'
            
            # Редактируем сообщение с выбором теста на первый вопрос
            await self.send_question(query, context)
        
        elif data.startswith("answer_"):
            # Обработка ответа
            answer = 1 if "yes" in data else 0
            current_question = context.user_data['current_question']
            
            # Сохраняем ответ
            context.user_data['test_answers'].append({
                'question_number': current_question + 1,
                'answer': answer
            })
            
            # Переходим к следующему вопросу
            context.user_data['current_question'] += 1
            
            # Проверяем, закончились ли вопросы
            if context.user_data['current_question'] < len(self.questions):
                # Редактируем текущее сообщение на следующий вопрос
                await self.send_question(query, context)
            else:
                # Все вопросы отвечены - завершаем тест
                await query.edit_message_text(
                    "Поздравляем, вы завершили прохождение психологического теста! 🎉\n\n"
                    "Пожалуйста, дождитесь сохранения ваших результатов"
                )
                
                # Вызываем функцию сохранения
                await self.finish_test(query.from_user, context)

    async def handle_message(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Обработка текстовых сообщений"""
        message = update.message
        text = message.text.strip()
        
        # Проверка состояния регистрации
        if 'registration_step' in context.user_data:
            await self.handle_registration_step(update, context, text)
            return
        
        # Проверка ожидания имени студента для админской части
        if 'awaiting_name' in context.user_data and context.user_data['awaiting_name']:
            context.user_data['awaiting_name'] = False #убираем флажок ожидания имени из контекста пользователя
            #после предоставления ему данных о результатах конкретного студента
            await self.admin_handler.show_raw_data(
                update,
                student_name=text
            )
            return
    
    async def handle_registration_step(self, update: Update, context: ContextTypes.DEFAULT_TYPE, text: str):
        """Обработка шагов регистрации"""
        step = context.user_data['registration_step']
        
        if step == 'ask_name':
            # Сохраняем имя и запрашиваем факультет
            context.user_data['full_name'] = text
            
            keyboard = [
                [InlineKeyboardButton("Радио и Телевидение", callback_data="reg_faculty_radio")],
                [InlineKeyboardButton("Информационные Технологии", callback_data="reg_faculty_it")],
                [InlineKeyboardButton("Сети и Системы Связи", callback_data="reg_faculty_networks")],
                [InlineKeyboardButton("Кибернетика и Информационная Безопасность", callback_data="reg_faculty_cyber")],
                [InlineKeyboardButton("Цифровая экономика и массовые коммуникации", callback_data="reg_faculty_digEco")]
            ]
            reply_markup = InlineKeyboardMarkup(keyboard)
            
            await update.message.reply_text(
                "Выберите ваш факультет:",
                reply_markup=reply_markup
            )
            context.user_data['registration_step'] = 'ask_faculty'
        
        elif step == 'ask_group':
            text = text.upper()  # Приводим к верхнему регистру
            
            # Простая проверка - группа должна содержать хотя бы одну русскую букву и одну цифру
            has_russian = False
            has_digit = False
            
            for char in text:
                if 'А' <= char <= 'Я':
                    has_russian = True
                elif char.isdigit():
                    has_digit = True
            
            if not (has_russian and has_digit):
                await update.message.reply_text(
                    "Неверный формат группы. Введите группу в формате БСТ2201 (русские буквы + цифры):"
                )
                return
            
            context.user_data['group'] = text
            
            # Запрашиваем подтверждение
            keyboard = [[InlineKeyboardButton("Подтверждаю", callback_data="reg_confirm")]]
            reply_markup = InlineKeyboardMarkup(keyboard)
            
            await update.message.reply_text(
                "Подтвердите своё согласие на прохождение тестирования "
                "и обработку персональных данных:",
                reply_markup=reply_markup
            )
    
    async def send_question(self, query, context):
        """Отправка/редактирование вопроса теста"""
        current_question = context.user_data['current_question']
        question_text = self.questions[current_question]
        
        keyboard = [
            [InlineKeyboardButton("✅ Да", callback_data="answer_yes")],
            [InlineKeyboardButton("❌ Нет", callback_data="answer_no")]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        progress = f"Вопрос {current_question + 1}/{len(self.questions)}"
        
        # Всегда редактируем текущее сообщение
        await query.edit_message_text(
            f"{progress}\n\n{question_text}",
            reply_markup=reply_markup
        )
    
    def calculate_scores(self, answers):
        """Расчет баллов по шкалам агрессивности"""
        scoring_rules = {
            'physical_aggression': {'yes': [1, 25, 33, 48, 55, 62, 68], 'no': [9, 17, 41]},
            'indirect_aggression': {'yes': [2, 18, 34, 42, 56, 63], 'no': [10, 26, 49]},
            'irritation': {'yes': [3, 19, 27, 43, 50, 57, 64, 72], 'no': [11, 35, 69]},
            'negativism': {'yes': [4, 12, 20, 23, 36]},
            'resentment': {'yes': [5, 13, 21, 29, 37, 51, 58], 'no': [44]},
            'suspicion': {'yes': [6, 14, 22, 30, 38, 45, 52, 59], 'no': [65, 70]},
            'verbal_aggression': {'yes': [7, 15, 23, 31, 46, 53, 60, 71, 73], 'no': [39, 74, 75]},
            'guilt': {'yes': [8, 16, 24, 32, 40, 47, 54, 61, 67]}
        }
        
        scores = {scale: 0 for scale in scoring_rules.keys()}
        
        for answer in answers:
            question_num = answer['question_number']
            user_answer = answer['answer']
            
            for scale, rules in scoring_rules.items():
                if 'yes' in rules and question_num in rules['yes'] and user_answer == 1:
                    scores[scale] += 1
                if 'no' in rules and question_num in rules['no'] and user_answer == 0:
                    scores[scale] += 1
        
        # Расчет индексов
        aggression_index = (scores['physical_aggression'] + 
                          scores['indirect_aggression'] + 
                          scores['verbal_aggression'])
        
        hostility_index = scores['resentment'] + scores['suspicion']
        
        scores['aggression_index'] = aggression_index
        scores['hostility_index'] = hostility_index
        
        return scores
    
    async def finish_test(self, user, context):  
        """Завершение теста и сохранение результатов"""
        try:
            tg_id = user.id  #тг id пользователя 
            answers = context.user_data['test_answers']
            
            # Проверяем, есть ли данные пользователя
            if not all(key in context.user_data for key in ['full_name', 'group', 'faculty']):
                # Нужно отправить сообщение, но у нас нет message объекта
                # Можно отправить через context.bot
                await context.bot.send_message(
                    chat_id=tg_id,
                    text="Ошибка: данные пользователя не найдены. Пожалуйста, начните сначала с команды /start"
                )
                return
            
            # Расчет результатов
            scores = self.calculate_scores(answers)
            
           
            user_saved = self.save_user(
                telegram_id=tg_id,
                full_name=context.user_data['full_name'],
                user_group=context.user_data['group'],
                faculty=context.user_data['faculty']
            )
            
            if not user_saved:
                await context.bot.send_message(
                    chat_id=tg_id,
                    text="Ошибка при сохранении данных пользователя."
                )
                return
            
            # Сохранение результатов теста в БД
            success = self.save_test_result(tg_id, scores)
            
            if success:
                await context.bot.send_message(
                    chat_id=tg_id,
                    text="✅ Ваши результаты успешно сохранены и будут доступны психологической службе."
                )
            else:
                await context.bot.send_message(
                    chat_id=tg_id,
                    text="Произошла ошибка при сохранении результатов. "
                )
        
        except Exception as e:
            logger.error(f"Ошибка при завершении теста: {e}")
            await context.bot.send_message(
                chat_id=tg_id,
                text="Произошла непредвиденная ошибка."
            )
        
        finally:
            # Очищаем данные пользователя
            for key in ['test_answers', 'current_question', 'test_type', 
                        'full_name', 'group', 'faculty', 'registration_step']:
                context.user_data.pop(key, None)

    def get_test_questions(self):
        """Возвращает список вопросов теста"""
        return [
            "Временами я не могу справиться с желанием причинить вред другим",
            "Иногда сплетничаю о людях, которых не люблю",
            "Я легко раздражаюсь, но быстро успокаиваюсь",
            "Если меня не попросят по-хорошему, я не выполню",
            "Я не всегда получаю то, что мне положено",
            "Я не знаю, что люди говорят обо мне за моей спиной",
            "Если я не одобряю поведение друзей, я даю им это почувствовать",
            "Когда мне случалось обмануть кого-нибудь, я испытывал мучительные угрызения совести",
            "Мне кажется, что я не способен ударить человека",
            "Я никогда не раздражаюсь настолько, чтобы кидаться предметами",
            "Я всегда снисходителен к чужим недостаткам",
            "Если мне не нравится установленное правило, мне хочется нарушить его",
            "Другие умеют почти всегда пользоваться благоприятными обстоятельствами",
            "Я держусь настороженно с людьми, которые относятся ко мне несколько более дружественно, чем я ожидал",
            "Я часто бываю не согласен с людьми",
            "Иногда мне на ум приходят мысли, которых я стыжусь",
            "Если кто-нибудь первым ударит меня, я не отвечу ему",
            "Когда я раздражаюсь, я хлопаю дверьми",
            "Я гораздо более раздражителен, чем кажется",
            "Если кто-то воображает себя начальником, я всегда поступаю ему наперекор",
            "Меня немного огорчает моя судьба",
            "Я думаю, что многие люди не любят меня",
            "Я не могу удержаться от спора, если люди не согласны со мной",
            "Люди, увиливающие от работы, должны испытывать чувство вины",
            "Тот, кто оскорбляет меня и мою семью, напрашивается на драку",
            "Я не способен на грубые шутки",
            "Меня охватывает ярость, когда надо мной насмехаются",
            "Когда люди строят из себя начальников, я делаю все, чтобы они не зазнавались",
            "Почти каждую неделю я вижу кого-нибудь, кто мне не нравится",
            "Довольно многие люди завидуют мне",
            "Я требую, чтобы люди уважали меня",
            "Меня угнетает то, что я мало делаю для своих родителей",
            "Люди, которые постоянно изводят вас, стоят того, чтобы их 'щелкнули по носу'",
            "Я никогда не бываю мрачен от злости",
            "Если ко мне относятся хуже, чем я того заслуживаю, я не расстраиваюсь",
            "Если кто-то выводит меня из себя, я не обращаю внимания",
            "Хотя я и не показываю этого, меня иногда гложет зависть",
            "Иногда мне кажется, что надо мной смеются",
            "Даже если я злюсь, я не прибегаю к 'сильным' выражениям",
            "Мне хочется, чтобы мои грехи были прощены",
            "Я редко даю сдачи, даже если кто-нибудь ударит меня",
            "Когда получается не по-моему, я иногда обижаюсь",
            "Иногда люди раздражают меня одним своим присутствием",
            "Нет людей, которых бы я по-настоящему ненавидел",
            "Мой принцип: 'Никогда не доверять чужакам'",
            "Если кто-нибудь раздражает меня, я готов сказать, что я о нем думаю",
            "Я делаю много такого, о чем впоследствии жалею",
            "Если я разозлюсь, я могу ударить кого-нибудь",
            "С детства я никогда не проявлял вспышек гнева",
            "Я часто чувствую себя как пороховая бочка, готовая взорваться",
            "Если бы все знали, что я чувствую, меня бы считали человеком, с которым нелегко работать",
            "Я всегда думаю о том, какие тайные причины заставляют людей делать что-нибудь приятное для меня",
            "Когда на меня кричат, я начинаю кричать в ответ",
            "Неудачи огорчают меня",
            "Я дерусь не реже и не чаще, чем другие",
            "Я могу вспомнить случаи, когда я был настолько зол, что хватал попавшуюся мне под руку вещь и ломал ее",
            "Иногда я чувствую, что готов первым начать драку",
            "Иногда я чувствую, что жизнь поступает со мной несправедливо",
            "Раньше я думал, что большинство людей говорит правду, но теперь я в это не верю",
            "Я ругаюсь только со злости",
            "Когда я поступаю неправильно, меня мучает совесть",
            "Если для защиты своих прав мне нужно применить физическую силу, я применяю ее",
            "Иногда я выражаю свой гнев тем, что стучу кулаком по столу",
            "Я бываю грубоват по отношению к людям, которые мне не нравятся",
            "У меня нет врагов, которые бы хотели мне навредить",
            "Я не умею поставить человека на место, даже если он того заслуживает",
            "Я часто думаю, что жил неправильно",
            "Я знаю людей, которые способны довести меня до драки",
            "Я не огорчаюсь из-за мелочей",
            "Мне редко приходит в голову, что люди пытаются разозлить или оскорбить меня",
            "Я часто только угрожаю людям, хотя и не собираюсь приводить угрозы в исполнение",
            "В последнее время я стал занудой",
            "В споре я часто повышаю голос",
            "Я стараюсь обычно скрывать свое плохое отношение к людям",
            "Я лучше соглашусь с чем-либо, чем стану спорить"
        ]
    
    def run(self):
        """Запуск бота"""
        self.application.run_polling(
            poll_interval=1,
            timeout=10,
            drop_pending_updates=True,
            allowed_updates=Update.ALL_TYPES
        )

if __name__ == "__main__":
    # Импортируем токен
    from tokenbot import tokenbot
    
    bot = PsychBot(tokenbot)
    bot.init()
    bot.run()