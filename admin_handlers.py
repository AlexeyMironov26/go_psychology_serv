import sqlite3
import json
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes
import logging
import pandas as pd
from io import BytesIO
import datetime
import openpyxl  



ADMIN_IDS = [475439608, 1489252140, 1461136014] 

class AdminHandler:
    # Словарь кодов факультетов
    faculty_codes = {
            "Радио и Телевидение": "1",
            "Информационные Технологии": "2", 
            "Сети и Системы Связи": "3",
            "Кибернетика и Информационная Безопасность": "4",
            "Цифровая экономика и массовые коммуникации": "5"
        }
    
    code_to_faculty = {v: k for k, v in faculty_codes.items()}

    valid_test_types = ["agg"]

    def __init__(self, db_path='psych_bot.db'):
        self.db_path = db_path
    
    def is_admin(self, telegram_id):
        """Проверка, является ли пользователь администратором"""
        return telegram_id in ADMIN_IDS
    
    async def admin_start(self, message, context=None):
        """Начало работы для администратора"""
        # Обрабатываем оба варианта: Update или Message
        if hasattr(message, 'effective_user'):
            # Это Update
            telegram_id = message.effective_user.id
            message = message.message
        elif hasattr(message, 'from_user'):
            # Это Message или CallbackQuery
            telegram_id = message.from_user.id
            message = message
        else:
            # Неизвестный тип
            return
        
        if not self.is_admin(telegram_id):
            await message.reply_text("Извините, вы не админ и поэтому вам отказано в доступе:/")
            return
        
        keyboard = [
            [InlineKeyboardButton("📊 Средние значения по факультету", callback_data="admin_faculty_avg")],
            [InlineKeyboardButton("🏫 Средние значения по всем факультетам", callback_data="admin_all_avg")],
            [InlineKeyboardButton("📈 Сырые результаты студентов", callback_data="admin_raw_results")]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await message.reply_text(
            "У вас есть доступ к результатам психологических тестов студентов МТУСИ, "
            "вы можете использовать одну из следующих команд, нажав на кнопку с соответствующим названием:\n\n"
            "1. 📊 Средние значения по факультету - получить усредненные результаты тестов студентов по выбранному факультету\n"
            "2. 🏫 Средние значения по всем факультетам - получить усредненные результаты тестов студентов со всех факультетов\n"
            "3. 📈 Сырые результаты студентов - получить результаты тестов студентов в чистом виде"
            " (конкретного студента/всех студентов факультета/всех студентов)\n\n"
            "(если возникла ошибка или непредвиденая ситуация при взаимодействии с ботом,"
            " просто вернитесь в это меню, отправив команду /results)",
            reply_markup=reply_markup
        )
    
    async def show_admin_tests_menu(self, query, action_type):
        """Меню выбора теста для админских функций"""
        # Упрощаем callback_data
        if action_type == "faculty_avg":
            callback_data = "avg_aggression"  # Было: "faculty_avg_aggression"
        elif action_type == "all_avg":
            callback_data = "all_aggression"  # Было: "all_avg_aggression"
        elif action_type == "raw":
            callback_data = "raw_aggression"  # Было: "raw_aggression" (уже короткий)
        else:
            callback_data = "avg_aggression"
        
        keyboard = [
            [InlineKeyboardButton("Опросник исследования уровня агрессивности", 
                                callback_data=callback_data)],
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await query.edit_message_text(
            "Выберите тест, по которому вас интересуют результаты:",
            reply_markup=reply_markup
        )

    async def show_faculty_selection(self, query, test_type):
        """Выбор факультета"""
        keyboard = []
        for faculty_name, faculty_code in self.faculty_codes.items():
            #callback_data: "fac_1_agg"
            callback_data = f"fac_{faculty_code}_{test_type[:3]}" 
            
            keyboard.append([InlineKeyboardButton(faculty_name, callback_data=callback_data)])
        
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await query.edit_message_text(
            "Выберите факультет:",
            reply_markup=reply_markup
        )
    
    def get_faculty_averages(self, faculty=None):
        """Получение средних значений по факультету или всем факультетам"""
        conn = sqlite3.connect(self.db_path, timeout=30)
        cursor = conn.cursor()
        
        query = """
        SELECT 
            AVG(physical_aggression) as avg_phys,
            AVG(indirect_aggression) as avg_indirect,
            AVG(irritation) as avg_irritation,
            AVG(negativism) as avg_negativism,
            AVG(resentment) as avg_resentment,
            AVG(suspicion) as avg_suspicion,
            AVG(verbal_aggression) as avg_verbal,
            AVG(guilt) as avg_guilt,
            AVG(aggression_index) as avg_aggression_idx,
            AVG(hostility_index) as avg_hostility_idx,
            COUNT(*) as count
        FROM aggression_test_results atr
        JOIN users u ON atr.user_id = u.id
        """
        
        params = []
        if faculty:
            query += " WHERE u.faculty = ?"
            params.append(faculty)
        
        cursor.execute(query, params)
        result = cursor.fetchone()
        conn.close()
        
        if not result or result[10] == 0:
            return None
        
        return {
            'physical_aggression': round(result[0], 2),
            'indirect_aggression': round(result[1], 2),
            'irritation': round(result[2], 2),
            'negativism': round(result[3], 2),
            'resentment': round(result[4], 2),
            'suspicion': round(result[5], 2),
            'verbal_aggression': round(result[6], 2),
            'guilt': round(result[7], 2),
            'aggression_index': round(result[8], 2),
            'hostility_index': round(result[9], 2),
            'count': result[10]
        }
    
    async def show_faculty_averages(self, query, faculty_code, test_type):
        """Показать средние значения по факультету"""
        # Получаем оригинальное название факультета по коду
        faculty_name = self.code_to_faculty.get(faculty_code)  
        
        if not faculty_name:
            # Если mapping не найден, используем код
            faculty_name = f"Факультет {faculty_code}"
        
        if test_type not in self.valid_test_types:  # Проверяем сокращенный тип теста
            await query.message.reply_text("Тест пока не реализован")
            return
        
        averages = self.get_faculty_averages(faculty_name)  # Используем полное название
        
        if not averages:
            await query.message.reply_text("Нет данных по выбранному факультету")
            return
        
        text = f"📊 Средние значения для факультета '{faculty_name}':\n\n"
        
        scale_names = {
            'physical_aggression': 'Физическая агрессия',
            'indirect_aggression': 'Косвенная агрессия',
            'irritation': 'Раздражение',
            'negativism': 'Негативизм',
            'resentment': 'Обида',
            'suspicion': 'Подозрительность',
            'verbal_aggression': 'Вербальная агрессия',
            'guilt': 'Чувство вины'
        }
        
        for key, name in scale_names.items():
            text += f"{name}: {averages[key]} баллов\n"
        
        text += f"\n📈 Индекс агрессивности: {averages['aggression_index']}\n"
        text += f"📉 Индекс враждебности: {averages['hostility_index']}\n\n"
        
        # Нормы
        text += "Нормы:\n"
        text += "• Индекс агрессивности: 21 ± 4 (17-25)\n"
        text += "• Индекс враждебности: 6.5-7 ± 3 (3.5-10)\n\n"
        
        if averages['aggression_index'] > 25:
            text += "⚠️ Индекс агрессивности ПРЕВЫШАЕТ норму\n"
        elif averages['aggression_index'] < 17:
            text += "ℹ️ Индекс агрессивности НИЖЕ нормы\n"
        else:
            text += "✅ Индекс агрессивности в пределах нормы\n"
            
        if averages['hostility_index'] > 10:
            text += "⚠️ Индекс враждебности ПРЕВЫШАЕТ норму\n"
        elif averages['hostility_index'] < 3.5:
            text += "ℹ️ Индекс враждебности НИЖЕ нормы\n"
        else:
            text += "✅ Индекс враждебности в пределах нормы\n"
        
        text += f"\nВсего тестов: {averages['count']}"
        
        await query.message.reply_text(text)
    
    async def show_all_averages(self, query, test_type):
        """Показать средние значения по всем факультетам"""
        if test_type != "aggression":
            await query.message.reply_text("Тест пока не реализован")
            return
        
        averages = self.get_faculty_averages()
        
        if not averages:
            await query.message.reply_text("Нет данных в базе")
            return
        
        text = "📊 Средние значения по всем факультетам:\n\n"
        
        scale_names = {
            'physical_aggression': 'Физическая агрессия',
            'indirect_aggression': 'Косвенная агрессия',
            'irritation': 'Раздражение',
            'negativism': 'Негативизм',
            'resentment': 'Обида',
            'suspicion': 'Подозрительность',
            'verbal_aggression': 'Вербальная агрессия',
            'guilt': 'Чувство вины'
        }
        
        for key, name in scale_names.items():
            text += f"{name}: {averages[key]} баллов\n"
        
        text += f"\n📈 Индекс агрессивности: {averages['aggression_index']}\n"
        text += f"📉 Индекс враждебности: {averages['hostility_index']}\n\n"
        
        # Нормы
        text += "Нормы:\n"
        text += "• Индекс агрессивности: 21 ± 4 (17-25)\n"
        text += "• Индекс враждебности: 6.5-7 ± 3 (3.5-10)\n\n"
        
        # Проверка на превышение норм
        if averages['aggression_index'] > 25:
            text += "⚠️ Индекс агрессивности ПРЕВЫШАЕТ норму\n"
        elif averages['aggression_index'] < 17:
            text += "ℹ️ Индекс агрессивности НИЖЕ нормы\n"
        else:
            text += "✅ Индекс агрессивности в пределах нормы\n"
            
        if averages['hostility_index'] > 10:
            text += "⚠️ Индекс враждебности ПРЕВЫШАЕТ норму\n"
        elif averages['hostility_index'] < 3.5:
            text += "ℹ️ Индекс враждебности НИЖЕ нормы\n"
        else:
            text += "✅ Индекс враждебности в пределах нормы\n"
        
        text += f"\nВсего тестов: {averages['count']}"
        
        await query.message.reply_text(text)
    
    async def show_raw_data_menu(self, update):
        query=update.callback_query
        """Меню для сырых данных"""
        keyboard = [
            [InlineKeyboardButton("Данные конкретного студента", callback_data="raw_single")],
            [InlineKeyboardButton("Данные факультета", callback_data="raw_faculty")],
            [InlineKeyboardButton("Данные всех факультетов", callback_data="raw_all")],
        
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await query.edit_message_text(
            "Выберите тип данных:",
            reply_markup=reply_markup
        )
       
    
    
    def get_raw_data(self, student_name=None, faculty=None):
        """Получение сырых данных из БД"""
        conn = sqlite3.connect(self.db_path, timeout=10)
        cursor = conn.cursor()
        
        query = """
        SELECT 
            u.full_name,
            u.user_group,
            u.faculty,
            atr.completed_at,
            atr.physical_aggression,
            atr.indirect_aggression,
            atr.irritation,
            atr.negativism,
            atr.resentment,
            atr.suspicion,
            atr.verbal_aggression,
            atr.guilt,
            atr.aggression_index,
            atr.hostility_index
        FROM aggression_test_results atr
        JOIN users u ON atr.user_id = u.id
        WHERE 1=1
        """
        
        params = []
        
        if student_name:
            query += " AND LOWER(u.full_name) LIKE ?"
            params.append(f"%{student_name.lower()}%")
        
        if faculty:
            query += " AND u.faculty = ?"
            params.append(faculty)
        
        query += " ORDER BY atr.completed_at DESC"
        
        cursor.execute(query, params)
        results = cursor.fetchall()
        conn.close()
        return results
    
    def create_excel_from_results(self, results, faculty=None, student_name=None, logger=None):
        """Создает Excel файл из результатов"""
        if not results:
            return None
        
        try:
            # Названия колонок (должны совпадать с порядком в results)
            columns = [
                'ФИО', 
                'Группа', 
                'Факультет', 
                'Дата тестирования',
                'Физическая агрессия', 
                'Косвенная агрессия', 
                'Раздражение',
                'Негативизм', 
                'Обида', 
                'Подозрительность', 
                'Вербальная агрессия', 
                'Чувство вины',
                'Индекс агрессивности', 
                'Индекс враждебности'
            ]
            
            # Создаем DataFrame
            df = pd.DataFrame(results, columns=columns)
            
            # Создаем Excel в памяти
            excel_buffer = BytesIO()
            
            with pd.ExcelWriter(excel_buffer, engine='openpyxl') as writer:
                df.to_excel(writer, sheet_name='Результаты тестов', index=False)
                
                # Получаем лист для форматирования
                worksheet = writer.sheets['Результаты тестов']
                
                # Автоматическая ширина колонок
                for column in worksheet.columns:
                    max_length = 0
                    column_letter = column[0].column_letter
                    for cell in column:
                        try:
                            if cell.value:
                                cell_length = len(str(cell.value))
                                if cell_length > max_length:
                                    max_length = cell_length
                        except:
                            pass
                    adjusted_width = min(max_length + 2, 50)
                    worksheet.column_dimensions[column_letter].width = adjusted_width
            
            excel_buffer.seek(0)
            return excel_buffer
            
        except Exception as e:
            logger.error(f"Ошибка создания Excel: {e}")
            return None
        
    async def show_raw_data(self, update, faculty=None, student_name=None):
        """Показать сырые данные в Excel файле"""
        logger1 = logging.getLogger(__name__)
        
        # Извлекаем message из update
        if update.callback_query:
            message = update.callback_query.message
            await update.callback_query.answer()
        elif update.message:
            message = update.message
        else:
            logger1.error("Не удалось извлечь сообщение из Update")
            return
        
        # Получаем данные
        results = self.get_raw_data(student_name=student_name, faculty=faculty)
        
        if not results:
            if student_name:
                await message.reply_text(f"Студент '{student_name}' не найден")
            else:
                await message.reply_text("Нет данных по выбранному критерию")
            return
        
        # Сообщаем о начале обработки
        status_msg = await message.reply_text(
            f"📊 Найдено {len(results)} записей\n"
            f"🔄 Создаю Excel файл..."
        )
        
        # Создаем Excel файл
        excel_buffer = self.create_excel_from_results(results, faculty, student_name, logger1)
        
        if not excel_buffer:
            await message.reply_text("❌ Ошибка при создании файла")
            return
        
        # Формируем имя файла
        timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M")
        
        if student_name:
            # Очищаем имя для файла
            clean_name = ''.join(c for c in student_name if c.isalnum() or c in (' ', '-', '_'))
            filename = f"данные_{clean_name}_{timestamp}.xlsx"
            caption = f"📊 Данные студента: {student_name}\n📁 Записей: {len(results)}"
            
        elif faculty:
            clean_faculty = ''.join(c for c in faculty if c.isalnum() or c in (' ', '-', '_'))
            filename = f"данные_{clean_faculty}_{timestamp}.xlsx"
            caption = f"📊 Данные факультета: {faculty}\n📁 Записей: {len(results)}"
            
        else:
            filename = f"все_данные_{timestamp}.xlsx"
            caption = f"📊 Все данные\n📁 Записей: {len(results)}"

        caption+=f"\n    Максимальные значения шкал: \nФизическая агрессия: 10,\
                            \nКосвенная агрессия: 9\
                            \nРаздражение: 11\
                            \nНегативизм: 5\
                            \nОбида: 8\
                            \nПодозрительность: 10\
                            \nВербальная агрессия: 12\
                            \nУгрызения совести, чувство вины: 9\
        \n\n    Норма агрессивности: 17-25\
        \n    Норма враждебности: 3.5-10"
        
        # Удаляем статус сообщение
        try:
            await status_msg.delete()
        except:
            pass
        
        # Отправляем файл
        await message.reply_document(
            document=excel_buffer,
            filename=filename,
            caption=caption
        )
