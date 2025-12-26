# import json
# import sqlite3
# from datetime import datetime
# import logging
# from tokenbot import tokenbot
# from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
# from telegram.ext import Application, CommandHandler, CallbackQueryHandler, ContextTypes
# import os

# # Настройка логирования
# logging.basicConfig(
#     format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
#     level=logging.INFO
# )

# class SimplePsychBot:
#     def __init__(self, token: str):
#         workers=(os.cpu_count() or 4)+2
#         self.application = Application.builder().token(token).concurrent_updates(workers).build()
#         self.init_database()  
#         self.setup_handlers()
        

#     def init_database(self):
#         """Инициализация базы данных SQLite"""
#         conn = sqlite3.connect('psych_bot.db')
#         cursor = conn.cursor()
        
#         cursor.execute('''
#             CREATE TABLE IF NOT EXISTS users (
#                 id INTEGER PRIMARY KEY AUTOINCREMENT,
#                 full_name TEXT,
#                 created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
#             )
#         ''')
        
#         cursor.execute('''
#             CREATE TABLE IF NOT EXISTS agression_test_results (
#                 id INTEGER PRIMARY KEY AUTOINCREMENT,
#                 user_id INTEGER,
#                 test_name TEXT,
#                 completed_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
#                 FOREIGN KEY (user_id) REFERENCES users (id)
#             )
#         ''')
        
#         conn.commit()
#         conn.close()

#     def save_user(self, telegram_id, username, full_name):
#         """Сохранить пользователя в БД"""
#         conn = sqlite3.connect('psych_bot.db')
#         cursor = conn.cursor()
        
#         cursor.execute('''
#             INSERT OR IGNORE INTO users (telegram_id, username, full_name)
#             VALUES (?, ?, ?)
#         ''', (telegram_id, username, full_name))
        
#         conn.commit()
#         conn.close()

#     def save_test_result(self, telegram_id, test_name, test_data):
#         """Сохранить результат теста"""
#         conn = sqlite3.connect('psych_bot.db')
#         cursor = conn.cursor()
        
#         cursor.execute('SELECT id FROM users WHERE telegram_id = ?', (telegram_id,))
#         user = cursor.fetchone()
        
#         if user:
#             user_id = user[0]
#             test_data_json = json.dumps(test_data, ensure_ascii=False)
            
#             cursor.execute('''
#                 INSERT INTO test_results (user_id, test_name, test_data)
#                 VALUES (?, ?, ?)
#             ''', (user_id, test_name, test_data_json))
        
#         conn.commit()
#         conn.close()

#     def get_user_results(self, telegram_id):
#         """Получить результаты пользователя"""
#         conn = sqlite3.connect('psych_bot.db')
#         cursor = conn.cursor()
        
#         cursor.execute('''
#             SELECT tr.test_name, tr.test_data, tr.completed_at 
#             FROM test_results tr
#             JOIN users u ON tr.user_id = u.id
#             WHERE u.telegram_id = ?
#             ORDER BY tr.completed_at DESC
#         ''', (telegram_id,))
        
#         results = cursor.fetchall()
#         conn.close()
#         return results

    
#     def setup_handlers(self):
#         self.application.add_handler(CommandHandler("start", self.start))
#         self.application.add_handler(CallbackQueryHandler(self.handle_callback, pattern="^.*$"))
    
#     async def start(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
#         """Главное меню"""
#         user = update.effective_user
#         self.save_user(user.id, user.username, user.full_name)  # ДОБАВЬ ЭТУ СТРОКУ
        
#         keyboard = [
#             [InlineKeyboardButton("ℹ️ О психологической службе", callback_data="info")],
#             [InlineKeyboardButton("📊 Тесты", callback_data="tests")],
#             [InlineKeyboardButton("📈 Мои результаты", callback_data="my_results")]  # НОВАЯ КНОПКА
#         ]
#         reply_markup = InlineKeyboardMarkup(keyboard)
        
#         await update.message.reply_text(
#             "Добро пожаловать в психологическую службу МТУСИ!",
#             reply_markup=reply_markup
#         )
    
#     async def show_my_results(self, query):
#         """Показать результаты пользователя"""
#         results = self.get_user_results(query.from_user.id)
        
#         if not results:
#             text = "📝 У вас пока нет пройденных тестов."
#             keyboard = [[InlineKeyboardButton("🔙 Назад", callback_data="back_to_menu")]]
#         else:
#             text = "📊 **Ваши результаты тестов:**\n\n"
            
#             for i, (test_name, test_data_json, completed_at) in enumerate(results[:10]):
#                 test_data = json.loads(test_data_json)
#                 text += f"**{test_name}**\n"
#                 text += f"📅 {completed_at}\n"
                
#                 if 'scores' in test_data:
#                     text += f"• Агрессивность: {test_data.get('aggression_index', 'N/A')}\n"
#                     text += f"• Враждебность: {test_data.get('hostility_index', 'N/A')}\n"
                
#                 text += "─" * 20 + "\n\n"
            
#             keyboard = [[InlineKeyboardButton("🔙 Назад", callback_data="back_to_menu")]]
        
#         reply_markup = InlineKeyboardMarkup(keyboard)
#         await query.edit_message_text(text, reply_markup=reply_markup, parse_mode='Markdown')


#     async def handle_callback(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
#         """Обработка всех callback'ов"""
#         query = update.callback_query
#         await query.answer()
        
#         data = query.data
        
#         if data == "info":
#             await self.show_info(query)
#         elif data == "tests":
#             await self.show_tests_menu(query)  # Новый метод для меню тестов
#         elif data == "my_results":  # ДОБАВЬ ЭТО УСЛОВИЕ
#             await self.show_my_results(query)
#         elif data == "aggression_test":
#             await self.start_aggression_test(query, context)  # Переименовали метод
#         elif data == "next_question":
#             await self.show_question(query, context)
#         elif data.startswith("answer_"):
#             await self.handle_test_answer(query, context)
#         elif data == "back_to_menu":
#             await self.back_to_menu(query)
#         elif data == "back_to_tests":  # Новая кнопка для возврата к списку тестов
#             await self.show_tests_menu(query)

#     async def show_tests_menu(self, query):
#         """Меню с доступными тестами"""
#         tests_menu_text = """
# 📊 **Доступные тесты**

# Выберите тест для прохождения:
#         """
        
#         keyboard = [
#             [InlineKeyboardButton("📝 Опросник агрессивности", callback_data="aggression_test")],
#             [InlineKeyboardButton("🔙 В главное меню", callback_data="back_to_menu")]
#         ]
        
#         reply_markup = InlineKeyboardMarkup(keyboard)
#         await query.edit_message_text(tests_menu_text, reply_markup=reply_markup, parse_mode='Markdown')

#     async def show_info(self, query):
#         """Показать информацию о службе"""
#         info_text = """
# 🏫 Психологическая служба МТУСИ

# Мы помогаем студентам:
# • Справиться со стрессом и тревогой
# • Наладить отношения с окружающими
# • Адаптироваться к учебному процессу
# • Решить личные проблемы

# 📍 Кабинет: 123, 1 этаж
# 📞 Телефон: +7 (495) 957-77-00
#         """
        
#         keyboard = [
#             [InlineKeyboardButton("🔙 Назад", callback_data="back_to_menu")]
#         ]
#         reply_markup = InlineKeyboardMarkup(keyboard)
        
#         await query.edit_message_text(info_text, reply_markup=reply_markup)

#     async def start_aggression_test(self, query, context):
#         """Начать опросник агрессивности"""
#         context.user_data['test_answers'] = []
#         context.user_data['current_question'] = 0
#         context.user_data['test_questions'] = self.get_test_questions()
        
#         # Инструкция
#         instruction = """
# 📋 **Опросник уровня агрессивности**

# **Инструкция:**
# Отметьте «да», если вы согласны с утверждением, и «нет» - если не согласны.
# Старайтесь долго над вопросами не раздумывать.

# Опросник содержит 75 вопросов.
#         """
        
#         keyboard = [
#             [InlineKeyboardButton("▶️ Начать тест", callback_data="next_question")],
#             [InlineKeyboardButton("🔙 К списку тестов", callback_data="back_to_tests")]
#         ]
#         reply_markup = InlineKeyboardMarkup(keyboard)
        
#         await query.edit_message_text(instruction, reply_markup=reply_markup, parse_mode='Markdown')

#     # Все остальные методы остаются без изменений:
#     def get_test_questions(self):
#         """Возвращает список всех 75 вопросов опросника"""
#         return [
#             "Временами я не могу справиться с желанием причинить вред другим",
#             "Иногда сплетничаю о людях, которых не люблю",
#             "Я легко раздражаюсь, но быстро успокаиваюсь",
#             "Если меня не попросят по-хорошему, я не выполню",
#             "Я не всегда получаю то, что мне положено",
#             "Я не знаю, что люди говорят обо мне за моей спиной",
#             "Если я не одобряю поведение друзей, я даю им это почувствовать",
#             "Когда мне случалось обмануть кого-нибудь, я испытывал мучительные угрызения совести",
#             "Мне кажется, что я не способен ударить человека",
#             "Я никогда не раздражаюсь настолько, чтобы кидаться предметами",
#             "Я всегда снисходителен к чужим недостаткам",
#             "Если мне не нравится установленное правило, мне хочется нарушить его",
#             "Другие умеют почти всегда пользоваться благоприятными обстоятельствами",
#             "Я держусь настороженно с людьми, которые относятся ко мне несколько более дружественно, чем я ожидал",
#             "Я часто бываю не согласен с людьми",
#             "Иногда мне на ум приходят мысли, которых я стыжусь",
#             "Если кто-нибудь первым ударит меня, я не отвечу ему",
#             "Когда я раздражаюсь, я хлопаю дверьми",
#             "Я гораздо более раздражителен, чем кажется",
#             "Если кто-то воображает себя начальником, я всегда поступаю ему наперекор",
#             "Меня немного огорчает моя судьба",
#             "Я думаю, что многие люди не любят меня",
#             "Я не могу удержаться от спора, если люди не согласны со мной",
#             "Люди, увиливающие от работы, должны испытывать чувство вины",
#             "Тот, кто оскорбляет меня и мою семью, напрашивается на драку",
#             "Я не способен на грубые шутки",
#             "Меня охватывает ярость, когда надо мной насмехаются",
#             "Когда люди строят из себя начальников, я делаю все, чтобы они не зазнавались",
#             "Почти каждую неделю я вижу кого-нибудь, кто мне не нравится",
#             "Довольно многие люди завидуют мне",
#             "Я требую, чтобы люди уважали меня",
#             "Меня угнетает то, что я мало делаю для своих родителей",
#             "Люди, которые постоянно изводят вас, стоят того, чтобы их 'щелкнули по носу'",
#             "Я никогда не бываю мрачен от злости",
#             "Если ко мне относятся хуже, чем я того заслуживаю, я не расстраиваюсь",
#             "Если кто-то выводит меня из себя, я не обращаю внимания",
#             "Хотя я и не показываю этого, меня иногда гложет зависть",
#             "Иногда мне кажется, что надо мной смеются",
#             "Даже если я злюсь, я не прибегаю к 'сильным' выражениям",
#             "Мне хочется, чтобы мои грехи были прощены",
#             "Я редко даю сдачи, даже если кто-нибудь ударит меня",
#             "Когда получается не по-моему, я иногда обижаюсь",
#             "Иногда люди раздражают меня одним своим присутствием",
#             "Нет людей, которых бы я по-настоящему ненавидел",
#             "Мой принцип: 'Никогда не доверять чужакам'",
#             "Если кто-нибудь раздражает меня, я готов сказать, что я о нем думаю",
#             "Я делаю много такого, о чем впоследствии жалею",
#             "Если я разозлюсь, я могу ударить кого-нибудь",
#             "С детства я никогда не проявлял вспышек гнева",
#             "Я часто чувствую себя как пороховая бочка, готовая взорваться",
#             "Если бы все знали, что я чувствую, меня бы считали человеком, с которым нелегко работать",
#             "Я всегда думаю о том, какие тайные причины заставляют людей делать что-нибудь приятное для меня",
#             "Когда на меня кричат, я начинаю кричать в ответ",
#             "Неудачи огорчают меня",
#             "Я дерусь не реже и не чаще, чем другие",
#             "Я могу вспомнить случаи, когда я был настолько зол, что хватал попавшуюся мне под руку вещь и ломал ее",
#             "Иногда я чувствую, что готов первым начать драку",
#             "Иногда я чувствую, что жизнь поступает со мной несправедливо",
#             "Раньше я думал, что большинство людей говорит правду, но теперь я в это не верю",
#             "Я ругаюсь только со злости",
#             "Когда я поступаю неправильно, меня мучает совесть",
#             "Если для защиты своих прав мне нужно применить физическую силу, я применяю ее",
#             "Иногда я выражаю свой гнев тем, что стучу кулаком по столу",
#             "Я бываю грубоват по отношению к людям, которые мне не нравятся",
#             "У меня нет врагов, которые бы хотели мне навредить",
#             "Я не умею поставить человека на место, даже если он того заслуживает",
#             "Я часто думаю, что жил неправильно",
#             "Я знаю людей, которые способны довести меня до драки",
#             "Я не огорчаюсь из-за мелочей",
#             "Мне редко приходит в голову, что люди пытаются разозлить или оскорбить меня",
#             "Я часто только угрожаю людям, хотя и не собираюсь приводить угрозы в исполнение",
#             "В последнее время я стал занудой",
#             "В споре я часто повышаю голос",
#             "Я стараюсь обычно скрывать свое плохое отношение к людям",
#             "Я лучше соглашусь с чем-либо, чем стану спорить"
#         ]

    
#     async def show_question(self, query, context):
#         """Показать текущий вопрос"""
#         questions = context.user_data['test_questions']
#         current_question = context.user_data['current_question']
        
#         if current_question >= len(questions):
#             await self.calculate_results(query, context)
#             return
        
#         question = questions[current_question]
        
#         keyboard = [
#             [InlineKeyboardButton("✅ Да", callback_data="answer_1")],
#             [InlineKeyboardButton("❌ Нет", callback_data="answer_0")],
#             [InlineKeyboardButton("⏹️ Прервать тест", callback_data="back_to_tests")]
#         ]
        
#         reply_markup = InlineKeyboardMarkup(keyboard)
        
#         progress = f"({current_question + 1}/{len(questions)})"
        
#         await query.edit_message_text(
#             f"📊 Вопрос {progress}:\n\n{question}",
#             reply_markup=reply_markup
#         )
    
#     async def handle_test_answer(self, query, context):
#         """Обработка ответа на вопрос"""
#         answer = int(query.data.split("_")[1])  # 1 для "да", 0 для "нет"
        
#         current_question = context.user_data['current_question']
#         questions = context.user_data['test_questions']
        
#         # Сохраняем ответ
#         context.user_data['test_answers'].append({
#             'question_number': current_question + 1,
#             'question': questions[current_question],
#             'answer': answer
#         })
        
#         # Переходим к следующему вопросу
#         context.user_data['current_question'] += 1
        
#         # Показываем следующий вопрос
#         if context.user_data['current_question'] < len(questions):
#             await self.show_question(query, context)
#         else:
#             await self.calculate_results(query, context)
    
#     async def calculate_results(self, query, context):
#         """Расчет результатов по шкалам агрессивности"""
#         answers = context.user_data['test_answers']
        
#         # Правила подсчета баллов по шкалам
#         scoring_rules = {
#             'physical_aggression': {
#                 'yes': [1, 25, 33, 48, 55, 62, 68],
#                 'no': [9, 17, 41]
#             },
#             'indirect_aggression': {
#                 'yes': [2, 18, 34, 42, 56, 63],
#                 'no': [10, 26, 49]
#             },
#             'irritation': {
#                 'yes': [3, 19, 27, 43, 50, 57, 64, 72],
#                 'no': [11, 35, 69]
#             },
#             'negativism': {
#                 'yes': [4, 12, 20, 23, 36]
#             },
#             'resentment': {
#                 'yes': [5, 13, 21, 29, 37, 51, 58],
#                 'no': [44]
#             },
#             'suspicion': {
#                 'yes': [6, 14, 22, 30, 38, 45, 52, 59],
#                 'no': [65, 70]
#             },
#             'verbal_aggression': {
#                 'yes': [7, 15, 31, 46, 53, 60, 71, 73],
#                 'no': [39, 74, 75]
#             },
#             'guilt': {
#                 'yes': [8, 16, 24, 32, 40, 47, 54, 61, 67]
#             }
#         }
        
#         # Подсчет баллов по шкалам
#         scores = {scale: 0 for scale in scoring_rules.keys()}
        
#         for answer in answers:
#             question_num = answer['question_number']
#             user_answer = answer['answer']
            
#             for scale, rules in scoring_rules.items():
#                 # Подсчет за ответы "да"
#                 if 'yes' in rules and question_num in rules['yes'] and user_answer == 1:
#                     scores[scale] += 1
#                 # Подсчет за ответы "нет"  
#                 if 'no' in rules and question_num in rules['no'] and user_answer == 0:
#                     scores[scale] += 1
        
#         # Расчет индексов
#         aggression_index = (scores['physical_aggression'] + scores['irritation'] + 
#                           scores['verbal_aggression'])
#         hostility_index = scores['resentment'] + scores['suspicion']

#         test_data = {
#             'scores': scores,
#             'aggression_index': aggression_index,
#             'hostility_index': hostility_index,
#             'answers_count': len(answers)
#         }
#         self.save_test_result(query.from_user.id, "Опросник агрессивности", test_data)
        
#         await self.show_results(query, scores, aggression_index, hostility_index)
    
#     async def show_results(self, query, scores, aggression_index, hostility_index):
#         """Показать результаты теста"""
#         # Интерпретация результатов
#         scale_interpretation = {
#             'physical_aggression': "Физическая агрессия",
#             'indirect_aggression': "Косвенная агрессия", 
#             'irritation': "Раздражение",
#             'negativism': "Негативизм",
#             'resentment': "Обида",
#             'suspicion': "Подозрительность",
#             'verbal_aggression': "Вербальная агрессия",
#             'guilt': "Чувство вины"
#         }
        
#         result_text = "📊 **Результаты опросника агрессивности**\n\n"
        
#         # Показать баллы по шкалам
#         result_text += "**Баллы по шкалам:**\n"
#         for scale, score in scores.items():
#             result_text += f"• {scale_interpretation[scale]}: {score} баллов\n"
        
#         result_text += f"\n**Индекс агрессивности:** {aggression_index}\n"
#         result_text += f"**Индекс враждебности:** {hostility_index}\n"
        
#         # Общая интерпретация
#         result_text += "\n**Рекомендации:**\n"
#         if aggression_index <= 5 and hostility_index <= 3:
#             result_text += "✅ Низкий уровень агрессивности и враждебности. Вы хорошо контролируете свои эмоции."
#         elif aggression_index <= 10 and hostility_index <= 6:
#             result_text += "⚠️ Средний уровень. В целом нормальные показатели, но есть над чем работать."
#         else:
#             result_text += "❌ Повышенный уровень. Рекомендуется консультация психолога для работы с агрессивными проявлениями."
        
#         result_text += "\n\nДля подробной интерпретации результатов обратитесь к психологу."
        
#         keyboard = [
#             [InlineKeyboardButton("🔙 К списку тестов", callback_data="back_to_tests")],
#             [InlineKeyboardButton("🏠 В главное меню", callback_data="back_to_menu")]
#         ]
#         reply_markup = InlineKeyboardMarkup(keyboard)
        
#         await query.edit_message_text(result_text, reply_markup=reply_markup, parse_mode='Markdown')
    
#     async def back_to_menu(self, query):
#         """Вернуться в главное меню"""
#         keyboard = [
#             [InlineKeyboardButton("ℹ️ О психологической службе", callback_data="info")],
#             [InlineKeyboardButton("📊 Тесты", callback_data="tests")],
#             [InlineKeyboardButton("📈 Мои результаты", callback_data="my_results")]  # ДОБАВЬ ЭТУ СТРОКУ
#         ]
#         reply_markup = InlineKeyboardMarkup(keyboard)
        
#         await query.edit_message_text(
#             "Главное меню:",
#             reply_markup=reply_markup
#         )
    
#     def run(self):
#         self.application.run_polling()

# # Запуск бота
# if __name__ == "__main__":
#     bot = SimplePsychBot(tokenbot)
#     bot.run()