import logging
from tokenbot import tokenbot
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, CallbackQueryHandler, ContextTypes

# Настройка логирования
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)

class SimplePsychBot:
    def __init__(self, token: str):
        self.application = Application.builder().token(token).build()
        self.setup_handlers()
    
    def setup_handlers(self):
        self.application.add_handler(CommandHandler("start", self.start))
        self.application.add_handler(CallbackQueryHandler(self.handle_callback, pattern="^.*$"))
    
    async def start(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Главное меню"""
        keyboard = [
            [InlineKeyboardButton("ℹ️ О психологической службе", callback_data="info")],
            [InlineKeyboardButton("📊 Пройти тест", callback_data="start_test")]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await update.message.reply_text(
            "Добро пожаловать! Выберите опцию:",
            reply_markup=reply_markup
        )
    
    async def handle_callback(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Обработка всех callback'ов"""
        query = update.callback_query
        await query.answer()
        
        data = query.data
        
        if data == "info":
            await self.show_info(query)
        elif data == "start_test":
            await self.start_test(query, context)
        elif data.startswith("answer_"):
            await self.handle_test_answer(query, context)
        elif data == "back_to_menu":
            await self.back_to_menu(query)
    
    async def show_info(self, query):
        """Показать информацию о службе"""
        info_text = """
🏫 Психологическая служба МТУСИ

Мы помогаем студентам:
• Справиться со стрессом и тревогой
• Наладить отношения с окружающими
• Адаптироваться к учебному процессу
• Решить личные проблемы

📍 Кабинет: 123, 1 этаж
📞 Телефон: +7 (495) 957-77-00
        """
        
        keyboard = [[InlineKeyboardButton("🔙 Назад", callback_data="back_to_menu")]]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await query.edit_message_text(info_text, reply_markup=reply_markup)
    
    async def start_test(self, query, context):
        """Начать тест"""
        # Инициализируем данные теста
        context.user_data['test_answers'] = []
        context.user_data['current_question'] = 0
        
        # Вопросы теста
        questions = [
            {
                "text": "Как часто за последнюю неделю вы чувствовали себя счастливым?",
                "options": [
                    {"text": "Почти всегда", "score": 0},
                    {"text": "Часто", "score": 1},
                    {"text": "Иногда", "score": 2},
                    {"text": "Редко", "score": 3}
                ]
            },
            {
                "text": "Насколько хорошо вы спали последние дни?",
                "options": [
                    {"text": "Очень хорошо", "score": 0},
                    {"text": "Нормально", "score": 1},
                    {"text": "Плохо", "score": 2},
                    {"text": "Очень плохо", "score": 3}
                ]
            },
            {
                "text": "Как часто вы чувствовали тревогу или напряжение?",
                "options": [
                    {"text": "Почти никогда", "score": 0},
                    {"text": "Иногда", "score": 1},
                    {"text": "Часто", "score": 2},
                    {"text": "Постоянно", "score": 3}
                ]
            }
        ]
        
        context.user_data['test_questions'] = questions
        await self.show_question(query, context)
    
    async def show_question(self, query, context):
        """Показать текущий вопрос"""
        questions = context.user_data['test_questions']
        current_question = context.user_data['current_question']
        
        if current_question >= len(questions):
            await self.finish_test(query, context)
            return
        
        question = questions[current_question]
        
        keyboard = []
        for i, option in enumerate(question['options']):
            keyboard.append([InlineKeyboardButton(
                option['text'], 
                callback_data=f"answer_{i}"
            )])
        
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await query.edit_message_text(
            f"📊 Вопрос {current_question + 1}/{len(questions)}:\n\n{question['text']}",
            reply_markup=reply_markup
        )
    
    async def handle_test_answer(self, query, context):
        """Обработка ответа на вопрос"""
        answer_index = int(query.data.split("_")[1])
        current_question = context.user_data['current_question']
        questions = context.user_data['test_questions']
        
        # Сохраняем ответ
        question = questions[current_question]
        selected_option = question['options'][answer_index]
        
        context.user_data['test_answers'].append({
            'question': question['text'],
            'answer': selected_option['text'],
            'score': selected_option['score']
        })
        
        # Переходим к следующему вопросу
        context.user_data['current_question'] += 1
        await self.show_question(query, context)
    
    async def finish_test(self, query, context):
        """Завершить тест и показать результаты"""
        answers = context.user_data['test_answers']
        total_score = sum(answer['score'] for answer in answers)
        
        # Определяем результат
        if total_score <= 3:
            result = "✅ Отличное состояние! Вы хорошо справляетесь с нагрузками."
        elif total_score <= 6:
            result = "⚠️ Нормальное состояние. Есть небольшие трудности, но в целом всё хорошо."
        else:
            result = "❌ Рекомендуется обратиться к психологу. Вы испытываете значительный стресс."
        
        result_text = f"""
📊 Результаты теста:

• Набранные баллы: {total_score}/9
• {result}

💡 Рекомендация:
{result}

Если вы хотите обсудить результаты, обращайтесь в психологическую службу!
        """
        
        keyboard = [[InlineKeyboardButton("🔙 В главное меню", callback_data="back_to_menu")]]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await query.edit_message_text(result_text, reply_markup=reply_markup)
    
    async def back_to_menu(self, query):
        """Вернуться в главное меню"""
        keyboard = [
            [InlineKeyboardButton("ℹ️ О психологической службе", callback_data="info")],
            [InlineKeyboardButton("📊 Пройти тест", callback_data="start_test")]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await query.edit_message_text(
            "Выберите опцию:",
            reply_markup=reply_markup
        )
    
    def run(self):
        self.application.run_polling()

# Запуск бота
if __name__ == "__main__":
    bot = SimplePsychBot(tokenbot)
    bot.run()
