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

    valid_test_types = ["agg", "eye"]

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
        if action_type == "faculty_avg":
            agg_cb = "avg_aggression"
            eye_cb = "avg_eysenck"
        elif action_type == "all_avg":
            agg_cb = "all_aggression"
            eye_cb = "all_eysenck"
        else:  # raw
            agg_cb = "raw_aggression"
            eye_cb = "raw_eysenck"

        keyboard = [
            [InlineKeyboardButton("Опросник исследования уровня агрессивности", callback_data=agg_cb)],
            [InlineKeyboardButton("Опросник Айзенка (тип темперамента)", callback_data=eye_cb)],
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await query.edit_message_text(
            "Выберите тест, по которому вас интересуют результаты:",
            reply_markup=reply_markup
        )

    async def show_faculty_selection(self, query, test_type):
        """Выбор факультета. test_type: 'aggression', 'eysenck', 'raw'"""
        keyboard = []
        for faculty_name, faculty_code in self.faculty_codes.items():
            # aggression -> agg, eysenck -> eye, raw -> raw
            if test_type == 'eysenck':
                suffix = 'eye'
            else:
                suffix = test_type[:3]
            callback_data = f"fac_{faculty_code}_{suffix}"
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
            query += " WHERE COALESCE(atr.snapshot_faculty, u.faculty) = ?"
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
        faculty_name = self.code_to_faculty.get(faculty_code)
        if not faculty_name:
            faculty_name = f"Факультет {faculty_code}"
        
        if test_type == "eye":
            await self._show_eysenck_averages(query, faculty_name)
        elif test_type == "agg":
            await self._show_aggression_averages(query, faculty_name)
        else:
            await query.message.reply_text("Тест пока не реализован")

    async def _show_aggression_averages(self, query, faculty_name=None):
        """Вывод средних по тесту агрессии"""
        averages = self.get_faculty_averages(faculty_name)
        
        if not averages:
            label = f"факультету '{faculty_name}'" if faculty_name else "всем факультетам"
            await query.message.reply_text(f"Нет данных по {label}")
            return
        
        label = f"факультета '{faculty_name}'" if faculty_name else "всех факультетов"
        text = f"📊 Средние значения для {label}:\n\n"
        
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
        if test_type == "eysenck":
            await self._show_eysenck_averages(query, faculty_name=None)
        elif test_type == "aggression":
            await self._show_aggression_averages(query, faculty_name=None)
        else:
            await query.message.reply_text("Тест пока не реализован")
    
    async def show_raw_data_menu(self, update, test_type='aggression'):
        query = update.callback_query
        """Меню для сырых данных"""
        # Передаём test_type в callback через суффикс: raw_single_agg / raw_single_eye
        suffix = 'eye' if test_type == 'eysenck' else 'agg'
        keyboard = [
            [InlineKeyboardButton("Данные конкретного студента", callback_data=f"raw_single_{suffix}")],
            [InlineKeyboardButton("Данные факультета", callback_data=f"raw_faculty_{suffix}")],
            [InlineKeyboardButton("Данные всех факультетов", callback_data=f"raw_all_{suffix}")],
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await query.edit_message_text(
            "Выберите тип данных:",
            reply_markup=reply_markup
        )

    def get_eysenck_raw_data(self, student_name=None, faculty=None):
        """Получение сырых данных теста Айзенка из БД"""
        conn = sqlite3.connect(self.db_path, timeout=10)
        cursor = conn.cursor()
        
        query = """
        SELECT 
            COALESCE(etr.snapshot_full_name, u.full_name) AS full_name,
            COALESCE(etr.snapshot_user_group, u.user_group) AS user_group,
            COALESCE(etr.snapshot_faculty, u.faculty) AS faculty,
            etr.completed_at,
            etr.extraversion,
            etr.neuroticism,
            etr.lie
        FROM eysenck_test_results etr
        JOIN users u ON etr.user_id = u.id
        WHERE 1=1
        """
        
        params = []
        if student_name:
            query += " AND LOWER(COALESCE(etr.snapshot_full_name, u.full_name)) LIKE ?"
            params.append(f"%{student_name.lower()}%")
        if faculty:
            query += " AND COALESCE(etr.snapshot_faculty, u.faculty) = ?"
            params.append(faculty)
        
        query += " ORDER BY etr.completed_at DESC"
        
        cursor.execute(query, params)
        results = cursor.fetchall()
        conn.close()
        return results

    def get_eysenck_averages(self, faculty=None):
        """Средние значения теста Айзенка по факультету или всем"""
        conn = sqlite3.connect(self.db_path, timeout=30)
        cursor = conn.cursor()
        
        query = """
        SELECT
            AVG(extraversion),
            AVG(neuroticism),
            AVG(lie),
            COUNT(*)
        FROM eysenck_test_results etr
        JOIN users u ON etr.user_id = u.id
        """
        params = []
        if faculty:
            query += " WHERE COALESCE(etr.snapshot_faculty, u.faculty) = ?"
            params.append(faculty)
        
        cursor.execute(query, params)
        result = cursor.fetchone()
        conn.close()
        
        if not result or result[3] == 0:
            return None
        
        return {
            'extraversion': round(result[0], 2),
            'neuroticism': round(result[1], 2),
            'lie': round(result[2], 2),
            'count': result[3],
        }

    async def _show_eysenck_averages(self, query, faculty_name=None):
        """Вывод средних по тесту Айзенка"""
        averages = self.get_eysenck_averages(faculty_name)
        
        if not averages:
            label = f"факультету '{faculty_name}'" if faculty_name else "всем факультетам"
            await query.message.reply_text(f"Нет данных по {label}")
            return
        
        label = f"факультета '{faculty_name}'" if faculty_name else "всех факультетов"
        e = averages['extraversion']
        n = averages['neuroticism']
        lie = averages['lie']
        
        text = f"📊 Средние значения (тест Айзенка) для {label}:\n\n"
        text += f"Экстраверсия: {e} / 24\n"
        text += f"Нейротизм: {n} / 24\n"
        text += f"Шкала лжи: {lie} / 9\n\n"
        
        text += "Экстраверсия / Интроверсия (0–24 балла):\n"
        text += "• 15–24: Экстраверт\n"
        text += "• 11–14: Амбиверт\n"
        text += "• 0–10: Интроверт\n\n"
        if e >= 15:
            text += f"➡️ Среднее ({e}): Экстраверт\n\n"
        elif e >= 11:
            text += f"➡️ Среднее ({e}): Амбиверт\n\n"
        else:
            text += f"➡️ Среднее ({e}): Интроверт\n\n"
        
        text += "Нейротизм / Стабильность (0–24 балла):\n"
        text += "• 13–24: Высокий уровень нейротизма\n"
        text += "• 9–12: Средний уровень эмоциональности\n"
        text += "• 0–8: Эмоциональная устойчивость\n\n"
        if n >= 23:
            text += f"➡️ Среднее ({n}): Невротизм, граничащий с патологией\n\n"
        elif n >= 17:
            text += f"➡️ Среднее ({n}): Присутствуют отдельные признаки расшатанности нервной системы\n\n"
        elif n >= 11:
            text += f"➡️ Среднее ({n}): Эмоциональная впечатлительность\n\n"
        else: 
            text += f"➡️ Среднее ({n}): Эмоциональная устойчивость\n\n"
        
        text += "Шкала лжи (0–9 баллов):\n"
        text += "• 0–3: Искренность\n"
        text += "• 4–5: Нормальная искренность\n"
        text += "• 6–9: Неискренность\n\n"
        if lie <= 3:
            text += f"➡️ Среднее ({lie}): Искренность\n\n"
        elif lie <= 5:
            text += f"➡️ Среднее ({lie}): Нормальная искренность\n\n"
        else:
            text += f"➡️ Среднее ({lie}): Неискренность\n\n"
        
        text += f"Всего тестов: {averages['count']}"
        await query.message.reply_text(text)

    async def show_eysenck_raw_data(self, update, faculty=None, student_name=None):
        """Показать сырые данные теста Айзенка в Excel файле"""
        logger1 = logging.getLogger(__name__)
        
        if update.callback_query:
            message = update.callback_query.message
            await update.callback_query.answer()
        elif update.message:
            message = update.message
        else:
            return
        
        results = self.get_eysenck_raw_data(student_name=student_name, faculty=faculty)
        
        if not results:
            if student_name:
                await message.reply_text(f"Студент '{student_name}' не найден")
            else:
                await message.reply_text("Нет данных по выбранному критерию")
            return
        
        status_msg = await message.reply_text(
            f"📊 Найдено {len(results)} записей\n🔄 Создаю Excel файл..."
        )
        
        columns = ['ФИО', 'Группа', 'Факультет', 'Дата тестирования',
                   'Экстраверсия', 'Нейротизм', 'Шкала лжи']
        
        df = pd.DataFrame(results, columns=columns)
        excel_buffer = BytesIO()
        try:
            with pd.ExcelWriter(excel_buffer, engine='openpyxl') as writer:
                df.to_excel(writer, sheet_name='Результаты Айзенка', index=False)
                worksheet = writer.sheets['Результаты Айзенка']
                for column in worksheet.columns:
                    max_length = max(
                        (len(str(cell.value)) for cell in column if cell.value), default=0
                    )
                    worksheet.column_dimensions[column[0].column_letter].width = min(max_length + 2, 50)
            excel_buffer.seek(0)
        except Exception as e:
            logger1.error(f"Ошибка создания Excel Айзенка: {e}")
            await message.reply_text("❌ Ошибка при создании файла")
            return
        
        timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M")
        if student_name:
            clean = ''.join(c for c in student_name if c.isalnum() or c in (' ', '-', '_'))
            filename = f"айзенк_{clean}_{timestamp}.xlsx"
            caption = f"📊 Данные студента: {student_name}\n📁 Записей: {len(results)}"
        elif faculty:
            clean = ''.join(c for c in faculty if c.isalnum() or c in (' ', '-', '_'))
            filename = f"айзенк_{clean}_{timestamp}.xlsx"
            caption = f"📊 Данные факультета: {faculty}\n📁 Записей: {len(results)}"
        else:
            filename = f"айзенк_все_{timestamp}.xlsx"
            caption = f"📊 Все данные (тест Айзенка)\n📁 Записей: {len(results)}"
        
        caption += (
            "\n\nМаксимальные значения шкал:"
            "\nЭкстраверсия: 24"
            "\nНейротизм: 24"
            "\nШкала лжи: 9"
        )
        
        try:
            await status_msg.delete()
        except:
            pass
        
        await message.reply_document(
            document=excel_buffer,
            filename=filename,
            caption=caption
        )
       
    
    
    def get_raw_data(self, student_name=None, faculty=None):
        """Получение сырых данных из БД"""
        conn = sqlite3.connect(self.db_path, timeout=10)
        cursor = conn.cursor()
        
        # Используем snapshot_* поля — они хранят данные пользователя
        # на момент прохождения теста и не меняются при редактировании профиля.
        # Если snapshot пустой (старые записи до обновления), берём текущие данные из users.
        query = """
        SELECT 
            COALESCE(atr.snapshot_full_name, u.full_name) AS full_name,
            COALESCE(atr.snapshot_user_group, u.user_group) AS user_group,
            COALESCE(atr.snapshot_faculty, u.faculty) AS faculty,
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
            query += " AND LOWER(COALESCE(atr.snapshot_full_name, u.full_name)) LIKE ?"
            params.append(f"%{student_name.lower()}%")
        
        if faculty:
            query += " AND COALESCE(atr.snapshot_faculty, u.faculty) = ?"
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
