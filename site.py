import sys, os, asyncio, aiohttp, aiodns, string, ssl, random, json, traceback
from PyQt5.QtWidgets import (QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, 
                             QLabel, QLineEdit, QPushButton, QProgressBar, QTextEdit, QSpinBox, 
                             QFileDialog, QMessageBox, QTabWidget, QStyle, QDialog, QDialogButtonBox,
                             QGroupBox, QCheckBox)
from PyQt5.QtCore import Qt, QThread, pyqtSignal, QMutex, QSettings
from PyQt5.QtGui import QFont, QColor, QTextCharFormat, QIcon

class SettingsManager:
    """Класс для управления настройками приложения"""
    def __init__(self):
        self.settings = QSettings("DomainGenerator", "AppSettings")
        self.defaults = {
            'output_file': 'sites.txt',
            'check_file': 'sites.txt',
            'always_on_top': False,
            'max_workers': 200,
            'batch_size': 2000,
            'request_delay': 50,
            'max_memory': 512,  # в MB
            'window_geometry': None
        }
    
    def load(self):
        """Загрузка настроек"""
        settings = {}
        for key, default in self.defaults.items():
            value = self.settings.value(key, default)
            
            # Преобразование типов
            if isinstance(default, bool):
                settings[key] = self.settings.value(key, default, type=bool)
            elif isinstance(default, int):
                settings[key] = self.settings.value(key, default, type=int)
            elif isinstance(default, str):
                settings[key] = str(value)
            else:
                settings[key] = value
        
        return settings
    
    def save(self, settings):
        """Сохранение настроек"""
        for key, value in settings.items():
            self.settings.setValue(key, value)
        self.settings.sync()

class SettingsDialog(QDialog):
    def __init__(self, settings, parent=None):
        super().__init__(parent)
        self.settings = settings
        self.setWindowTitle("Настройки")
        self.setWindowIcon(QIcon.fromTheme("preferences-system", QApplication.style().standardIcon(QStyle.SP_FileDialogDetailedView)))
        self.init_ui()
        
    def init_ui(self):
        layout = QVBoxLayout()
        layout.setContentsMargins(10, 10, 10, 10)
        
        # Настройки файлов
        file_group = QGroupBox("Настройки файлов")
        file_layout = QVBoxLayout()
        
        # Файл результатов генерации
        gen_file_layout = QHBoxLayout()
        gen_file_layout.addWidget(QLabel("Файл результатов:"))
        self.gen_file_edit = QLineEdit(self.settings['output_file'])
        gen_file_layout.addWidget(self.gen_file_edit)
        self.gen_browse_btn = QPushButton("Обзор")
        self.gen_browse_btn.clicked.connect(lambda: self.browse_file(self.gen_file_edit, is_save=True))
        gen_file_layout.addWidget(self.gen_browse_btn)
        file_layout.addLayout(gen_file_layout)
        
        # Файл для проверки дубликатов
        check_file_layout = QHBoxLayout()
        check_file_layout.addWidget(QLabel("Файл для проверки:"))
        self.check_file_edit = QLineEdit(self.settings['check_file'])
        check_file_layout.addWidget(self.check_file_edit)
        self.check_browse_btn = QPushButton("Обзор")
        self.check_browse_btn.clicked.connect(lambda: self.browse_file(self.check_file_edit, is_save=False))
        check_file_layout.addWidget(self.check_browse_btn)
        file_layout.addLayout(check_file_layout)
        
        file_group.setLayout(file_layout)
        layout.addWidget(file_group)
        
        # Кнопка очистки файла
        self.clear_btn = QPushButton("Очистить файл результатов")
        self.clear_btn.clicked.connect(self.clear_file)
        layout.addWidget(self.clear_btn)
        
        # Настройки производительности
        perf_group = QGroupBox("Настройки производительности")
        perf_layout = QVBoxLayout()
        
        # Максимальное количество потоков
        workers_layout = QHBoxLayout()
        workers_layout.addWidget(QLabel("Максимальное количество потоков:"))
        self.workers_spin = QSpinBox()
        self.workers_spin.setRange(1, 1000)
        self.workers_spin.setValue(self.settings['max_workers'])
        workers_layout.addWidget(self.workers_spin)
        perf_layout.addLayout(workers_layout)
        
        # Размер батча
        batch_layout = QHBoxLayout()
        batch_layout.addWidget(QLabel("Размер батча доменов:"))
        self.batch_spin = QSpinBox()
        self.batch_spin.setRange(100, 10000)
        self.batch_spin.setValue(self.settings['batch_size'])
        batch_layout.addWidget(self.batch_spin)
        perf_layout.addLayout(batch_layout)
        
        # Задержка между запросами
        delay_layout = QHBoxLayout()
        delay_layout.addWidget(QLabel("Задержка между запросами (мс):"))
        self.delay_spin = QSpinBox()
        self.delay_spin.setRange(0, 1000)
        self.delay_spin.setValue(self.settings['request_delay'])
        delay_layout.addWidget(self.delay_spin)
        perf_layout.addLayout(delay_layout)
        
        perf_group.setLayout(perf_layout)
        layout.addWidget(perf_group)
        
        # Настройки окна
        window_group = QGroupBox("Настройки окна")
        window_layout = QVBoxLayout()
        
        # Окно поверх других
        self.always_on_top_check = QCheckBox("Окно всегда поверх других окон")
        self.always_on_top_check.setChecked(self.settings['always_on_top'])
        window_layout.addWidget(self.always_on_top_check)
        
        window_group.setLayout(window_layout)
        layout.addWidget(window_group)
        
        # Кнопки диалога
        button_box = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        button_box.accepted.connect(self.accept)
        button_box.rejected.connect(self.reject)
        layout.addWidget(button_box)
        
        self.setLayout(layout)
    
    def browse_file(self, target_edit, is_save=True):
        if is_save:
            filename, _ = QFileDialog.getSaveFileName(
                self, 
                "Сохранить файл результатов", 
                target_edit.text(), 
                "Текстовые файлы (*.txt)"
            )
        else:
            filename, _ = QFileDialog.getOpenFileName(
                self, 
                "Выберите файл для проверки", 
                target_edit.text(), 
                "Текстовые файлы (*.txt)"
            )
            
        if filename:
            target_edit.setText(filename)
    
    def clear_file(self):
        filename = self.gen_file_edit.text()
        if not filename:
            return
            
        reply = QMessageBox.question(
            self, 
            "Подтверждение очистки",
            f"Вы уверены, что хотите очистить файл {filename}? Все данные будут удалены!",
            QMessageBox.Yes | QMessageBox.No
        )
        
        if reply == QMessageBox.Yes:
            try:
                with open(filename, 'w') as f:
                    f.write("")
                QMessageBox.information(self, "Успех", f"Файл {filename} успешно очищен")
            except Exception as e:
                QMessageBox.critical(self, "Ошибка", f"Ошибка при очистке файла: {str(e)}")
    
    def get_settings(self):
        """Возвращает текущие настройки из диалога"""
        return {
            'output_file': self.gen_file_edit.text(),
            'check_file': self.check_file_edit.text(),
            'always_on_top': self.always_on_top_check.isChecked(),
            'max_workers': self.workers_spin.value(),
            'batch_size': self.batch_spin.value(),
            'request_delay': self.delay_spin.value(),
            'max_memory': self.settings['max_memory']  # Сохраняем без изменений
        }

class DomainGenerator(QThread):
    update_progress = pyqtSignal(int, int)
    update_log = pyqtSignal(str)
    update_stats = pyqtSignal(str)
    found_site = pyqtSignal(str)
    finished = pyqtSignal()
    
    def __init__(self, min_length, max_length, settings):
        super().__init__()
        self.min_length, self.max_length = min_length, max_length
        self.settings = settings
        self.output_file = settings['output_file']
        self.running = True
        self.checked_count, self.valid_count = 0, 0
        self.chars = string.ascii_lowercase + string.digits
        self.tlds = ['.com', '.org', '.net']
        self.file_mutex = QMutex()
        self.loop = None
        self.resolver = None
        self.tasks = []  # Для отслеживания активных задач
        self.total_domains = self.calculate_total()
    
    def calculate_total(self):
        total = 0
        for length in range(self.min_length, self.max_length + 1):
            total += (len(self.chars) ** length) * len(self.tlds)
        return total
    
    def generate_random_domain(self, length):
        name = ''.join(random.choices(self.chars, k=length))
        tld = random.choice(self.tlds)
        return name + tld
    
    def generate_domains_batch(self, batch_size):
        domains = []
        for _ in range(batch_size):
            length = random.randint(self.min_length, self.max_length)
            domains.append(self.generate_random_domain(length))
        return domains
    
    async def check_dns(self, domain):
        try:
            if not self.running:  # Проверяем флаг перед выполнением запроса
                return False, "Запрос отменен"
            
            result = await self.resolver.query(domain, 'A')
            if result:
                return True, f"DNS найден: {domain}"
            return False, f"DNS не найден: {domain}"
        except aiodns.error.DNSError as e:
            if e.args[0] == 4:
                return False, f"DNS домен не существует: {domain}"
            return False, f"DNS ошибка для {domain}: {str(e)}"
        except asyncio.CancelledError:
            return False, "DNS запрос отменен"
        except Exception as e:
            return False, f"Общая DNS ошибка для {domain}: {str(e)}"
    
    async def check_http(self, session, domain):
        try:
            async with session.get(
                f"https://{domain}", 
                timeout=aiohttp.ClientTimeout(total=10),
                allow_redirects=True,
                ssl=ssl.create_default_context()
            ) as r:
                if 200 <= r.status < 400:
                    self.save_working_domain(domain)
                    self.found_site.emit(domain)
                    return True, f"HTTPS доступен: {domain} (статус: {r.status})"
                return False, f"HTTPS недоступен: {domain} (статус: {r.status})"
        except aiohttp.ClientConnectorCertificateError:
            return await self.try_http(session, domain)
        except aiohttp.ClientConnectorError as e:
            return await self.try_http(session, domain)
        except asyncio.TimeoutError:
            return False, f"Таймаут HTTPS: {domain}"
        except Exception as e:
            return False, f"HTTPS ошибка для {domain}: {str(e)}"
    
    async def try_http(self, session, domain):
        try:
            async with session.get(
                f"http://{domain}", 
                timeout=aiohttp.ClientTimeout(total=10),
                allow_redirects=True
            ) as r:
                if 200 <= r.status < 400:
                    self.save_working_domain(domain)
                    self.found_site.emit(domain)
                    return True, f"HTTP доступен: {domain} (статус: {r.status})"
                return False, f"HTTP недоступен: {domain} (статус: {r.status})"
        except asyncio.TimeoutError:
            return False, f"Таймаут HTTP: {domain}"
        except Exception as e:
            return False, f"HTTP ошибка для {domain}: {str(e)}"
    
    def save_working_domain(self, domain):
        self.file_mutex.lock()
        try:
            with open(self.output_file, 'a') as f:
                f.write(f"{domain}\n")
                f.flush()
        finally:
            self.file_mutex.unlock()
        self.valid_count += 1
    
    async def process_domains(self, session, domains):
        working_count = 0
        
        for i, domain in enumerate(domains):
            if not self.running:
                break
                
            # Добавляем задержку для ограничения нагрузки
            if i % 10 == 0 and self.settings['request_delay'] > 0:
                await asyncio.sleep(self.settings['request_delay'] / 1000.0)
                
            try:
                dns_ok, dns_log = await self.check_dns(domain)
                self.update_log.emit(dns_log)
                
                if not dns_ok:
                    continue
                    
                http_ok, http_log = await self.check_http(session, domain)
                self.update_log.emit(http_log)
                
                if http_ok:
                    working_count += 1
            except (ConnectionResetError, aiohttp.ClientConnectionError):
                continue
            except Exception as e:
                self.update_log.emit(f"Ошибка при обработке домена {domain}: {str(e)}")
        
        self.checked_count += len(domains)
        self.update_progress.emit(self.checked_count, self.total_domains)
        self.update_stats.emit(f"Проверено: {self.checked_count}/{self.total_domains} | Рабочих: {self.valid_count}")
    
    async def run_async(self):
        try:
            self.resolver = aiodns.DNSResolver()
            self.resolver.nameservers = ['8.8.8.8', '1.1.1.1', '9.9.9.9', '1.0.0.1']
            
            # Тест DNS
            try:
                await asyncio.wait_for(
                    self.resolver.query("google.com", "A"),
                    timeout=5.0
                )
                self.update_log.emit("DNS проверка: google.com разрешен успешно")
            except (asyncio.TimeoutError, Exception) as e:
                self.update_log.emit(f"Ошибка DNS: {str(e)}")
                return
            
            connector = aiohttp.TCPConnector(
                limit_per_host=self.settings['max_workers'],
                ssl=False
            )
            
            async with aiohttp.ClientSession(
                connector=connector,
                headers={"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36"}
            ) as session:
                
                # Тест HTTP
                try:
                    async with session.get(
                        "https://google.com", 
                        timeout=aiohttp.ClientTimeout(total=10),
                        allow_redirects=True
                    ) as r:
                        if r.status == 200:
                            self.update_log.emit("Тест HTTP: Google доступен")
                        else:
                            self.update_log.emit(f"Тест HTTP: Google вернул статус {r.status}")
                            return
                except Exception as e:
                    self.update_log.emit(f"Ошибка при тесте HTTP: {str(e)}")
                    return
                
                sem = asyncio.Semaphore(self.settings['max_workers'])
                self.tasks = []  # Сбрасываем список задач
                
                while self.running and self.checked_count < self.total_domains:
                    domains = self.generate_domains_batch(min(self.settings['batch_size'], 1000))
                    
                    await sem.acquire()
                    task = asyncio.create_task(self.process_domains(session, domains))
                    task.add_done_callback(lambda _: sem.release())
                    self.tasks.append(task)
                
                # Ожидаем завершения всех задач
                await asyncio.gather(*self.tasks, return_exceptions=True)
        except asyncio.CancelledError:
            self.update_log.emit("Запрос на остановку принят")
        except Exception as e:
            self.update_log.emit(f"Критическая ошибка в run_async: {str(e)}\n{traceback.format_exc()}")
        finally:
            # Закрываем резолвер асинхронно
            if hasattr(self, 'resolver') and self.resolver:
                try:
                    await self.resolver.close()
                except Exception as e:
                    self.update_log.emit(f"Ошибка при закрытии резолвера: {str(e)}")
    
    def run(self):
        try:
            self.loop = asyncio.new_event_loop()
            asyncio.set_event_loop(self.loop)
            self.loop.run_until_complete(self.run_async())
            self.update_log.emit(f"Завершено! Рабочих сайтов: {self.valid_count}")
        except asyncio.CancelledError:
            self.update_log.emit("Генерация отменена пользователем")
        except Exception as e: 
            error_msg = f"Критическая ошибка в потоке: {str(e)}\n{traceback.format_exc()}"
            self.update_log.emit(error_msg)
            print(error_msg)
        finally: 
            self.finished.emit()
    
    def stop(self):
        """Остановка генерации"""
        self.running = False
        if self.loop and self.loop.is_running():
            try:
                # Отменяем только незавершенные задачи
                for task in self.tasks:
                    if not task.done():
                        task.cancel()
            except Exception as e:
                self.update_log.emit(f"Ошибка при отмене задач: {str(e)}")
            
            self.update_log.emit("Запрос на остановку отправлен...")

class CheckerTab(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.init_ui()
        
    def init_ui(self):
        layout = QVBoxLayout()
        layout.setContentsMargins(10, 10, 10, 10)
        
        # Группа действий
        action_group = QGroupBox("Действия")
        action_layout = QVBoxLayout()
        
        # Кнопки действий
        btn_layout = QHBoxLayout()
        self.check_btn = QPushButton("Проверить дубликаты")
        self.check_btn.clicked.connect(self.check_duplicates)
        btn_layout.addWidget(self.check_btn)
        
        self.remove_btn = QPushButton("Удалить дубликаты")
        self.remove_btn.clicked.connect(self.remove_duplicates)
        self.remove_btn.setEnabled(False)
        btn_layout.addWidget(self.remove_btn)
        
        action_layout.addLayout(btn_layout)
        action_group.setLayout(action_layout)
        layout.addWidget(action_group)
        
        # Группа лога
        log_group = QGroupBox("Лог проверки")
        log_layout = QVBoxLayout()
        self.log = QTextEdit()
        self.log.setReadOnly(True)
        log_layout.addWidget(self.log)
        log_group.setLayout(log_layout)
        layout.addWidget(log_group, 1)
        
        self.setLayout(layout)
    
    def get_check_file(self):
        main_window = self.window()
        if hasattr(main_window, 'app_settings'):
            return main_window.app_settings['check_file']
        return 'sites.txt'  # Значение по умолчанию
    
    def check_duplicates(self):
        try:
            filename = self.get_check_file()
            if not filename or not os.path.exists(filename):
                self.log.append("Файл не найден!")
                return
                
            with open(filename, 'r') as f:
                domains = [line.strip().lower() for line in f if line.strip()]
            
            unique_domains = []
            duplicates = {}
            duplicate_count = 0
            
            for domain in domains:
                if domain not in unique_domains:
                    unique_domains.append(domain)
                else:
                    duplicate_count += 1
                    if domain not in duplicates:
                        duplicates[domain] = 1
                    else:
                        duplicates[domain] += 1
            
            total = len(domains)
            unique_count = len(unique_domains)
            
            self.log.append(f"Проверка завершена:")
            self.log.append(f"Всего сайтов: {total}")
            self.log.append(f"Уникальных: {unique_count}")
            self.log.append(f"Дубликатов: {duplicate_count}")
            
            if duplicates:
                self.log.append("\nНайдены дубликаты:")
                for domain, count in duplicates.items():
                    self.log.append(f"  - {domain}: {count+1} повторений")
            
            if duplicate_count > 0:
                self.remove_btn.setEnabled(True)
                self.log.append("\nНажмите 'Удалить дубликаты' для очистки файла")
            else:
                self.remove_btn.setEnabled(False)
                self.log.append("\nДубликаты не найдены!")
                
        except Exception as e:
            self.log.append(f"Ошибка при проверке дубликатов: {str(e)}")
    
    def remove_duplicates(self):
        try:
            filename = self.get_check_file()
            if not filename or not os.path.exists(filename):
                self.log.append("Файл не найден!")
                return
                
            with open(filename, 'r') as f:
                domains = [line.strip().lower() for line in f if line.strip()]
            
            # Удаляем дубликаты с сохранением порядка
            unique_domains = []
            for domain in domains:
                if domain not in unique_domains:
                    unique_domains.append(domain)
            
            # Сохраняем уникальные домены
            with open(filename, 'w') as f:
                for domain in unique_domains:
                    f.write(f"{domain}\n")
            
            self.log.append(f"Удалено дубликатов: {len(domains) - len(unique_domains)}")
            self.log.append(f"Сохранено уникальных: {len(unique_domains)}")
            self.log.append("Файл успешно обновлен!")
            self.remove_btn.setEnabled(False)
            
        except Exception as e:
            self.log.append(f"Ошибка при удалении дубликатов: {str(e)}")

class GeneratorTab(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.worker = None
        self.init_ui()
        
    def init_ui(self):
        layout = QVBoxLayout()
        layout.setContentsMargins(10, 10, 10, 10)
        
        settings_group = QGroupBox("Параметры генерации")
        settings_layout = QVBoxLayout()
        
        len_layout = QHBoxLayout()
        len_layout.addWidget(QLabel("Мин. длина:"))
        self.min_spin = QSpinBox()
        self.min_spin.setRange(1, 5)
        self.min_spin.setValue(3)
        len_layout.addWidget(self.min_spin)
        
        len_layout.addWidget(QLabel("Макс. длина:"))
        self.max_spin = QSpinBox()
        self.max_spin.setRange(1, 5)
        self.max_spin.setValue(4)
        len_layout.addWidget(self.max_spin)
        settings_layout.addLayout(len_layout)
        
        tld_info = QLabel("Доменные зоны: .com, .org, .net (случайный выбор)")
        tld_info.setStyleSheet("color: #888; font-style: italic;")
        settings_layout.addWidget(tld_info)
        
        settings_group.setLayout(settings_layout)
        
        control_layout = QHBoxLayout()
        self.start_btn = QPushButton("Начать генерацию")
        self.start_btn.clicked.connect(self.start)
        self.stop_btn = QPushButton("Остановить")
        self.stop_btn.setEnabled(False)
        self.stop_btn.clicked.connect(self.stop)
        control_layout.addWidget(self.start_btn)
        control_layout.addWidget(self.stop_btn)
        
        self.progress = QProgressBar()
        self.progress.setRange(0, 100)
        self.progress.setAlignment(Qt.AlignCenter)
        self.progress.setValue(0)
        self.progress.setFormat("Ожидание запуска")
        
        self.status = QLabel("Готов к работе")
        self.status.setAlignment(Qt.AlignCenter)
        self.status.setStyleSheet("font-weight: bold;")
        
        log_group = QGroupBox("Лог выполнения")
        log_layout = QVBoxLayout()
        self.log = QTextEdit()
        self.log.setReadOnly(True)
        log_layout.addWidget(self.log)
        log_group.setLayout(log_layout)
        
        layout.addWidget(settings_group)
        layout.addLayout(control_layout)
        layout.addWidget(self.progress)
        layout.addWidget(self.status)
        layout.addWidget(log_group, 1)
        
        self.setLayout(layout)
    
    def get_output_file(self):
        main_window = self.window()
        if hasattr(main_window, 'app_settings'):
            return main_window.app_settings['output_file']
        return 'sites.txt'  # Значение по умолчанию
    
    def start(self):
        try:
            min_len = self.min_spin.value()
            max_len = self.max_spin.value()
            file = self.get_output_file()
            
            if min_len > max_len:
                QMessageBox.critical(self, "Ошибка", "Минимальная длина не может быть больше максимальной")
                return
                
            if min_len < 1 or max_len > 5:
                QMessageBox.critical(self, "Ошибка", "Длина домена должна быть от 1 до 5 символов")
                return
                
            if not file: 
                QMessageBox.critical(self, "Ошибка", "Укажите файл для сохранения результатов в настройках")
                return
            
            self.log.clear()
            self.start_btn.setEnabled(False)
            self.stop_btn.setEnabled(True)
            self.progress.setValue(0)
            self.log.append("Запуск случайной генерации доменов...")
            self.log.append(f"Диапазон длины: {min_len}-{max_len} символов")
            self.log.append(f"Доменные зоны: .com, .org, .net")
            self.log.append(f"Файл результатов: {file}")
            
            # Безопасное получение настроек
            main_window = self.window()
            if hasattr(main_window, 'app_settings'):
                settings = main_window.app_settings
                self.log.append(f"Настройки производительности: Потоки={settings['max_workers']}, "
                               f"Батч={settings['batch_size']}, "
                               f"Задержка={settings['request_delay']}мс")
            else:
                settings = {
                    'output_file': file,
                    'max_workers': 200,
                    'batch_size': 2000,
                    'request_delay': 50
                }
            
            if not os.path.exists(file):
                with open(file, 'w') as f:
                    self.log.append(f"Создан новый файл: {file}")
            
            chars_count = len(string.ascii_lowercase + string.digits)
            total = 0
            for length in range(min_len, max_len + 1):
                total += (chars_count ** length) * 3
            self.log.append(f"Всего возможных доменов: {total:,}")
            
            self.worker = DomainGenerator(min_len, max_len, settings)
            self.worker.update_progress.connect(self.update_progress)
            self.worker.update_log.connect(self.log.append)
            self.worker.update_stats.connect(self.status.setText)
            self.worker.found_site.connect(self.highlight_found_site)
            self.worker.finished.connect(self.task_finished)
            self.worker.start()
            
        except Exception as e:
            error_msg = f"Ошибка при запуске генерации: {str(e)}\n{traceback.format_exc()}"
            self.log.append(error_msg)
            print(error_msg)
            self.start_btn.setEnabled(True)
            self.stop_btn.setEnabled(False)
    
    def update_progress(self, current, total):
        if total > 0:
            percent = int(current / total * 100)
            self.progress.setValue(percent)
            self.progress.setFormat(f"{percent}% ({current}/{total})")
    
    def highlight_found_site(self, domain):
        cursor = self.log.textCursor()
        cursor.movePosition(cursor.End)
        
        format = QTextCharFormat()
        format.setForeground(QColor("#00ff00"))
        format.setFontWeight(QFont.Bold)
        
        cursor.insertText(f"✓ Рабочий сайт: {domain}\n", format)
        self.log.ensureCursorVisible()
    
    def task_finished(self):
        self.start_btn.setEnabled(True)
        self.stop_btn.setEnabled(False)
        self.log.append("Генерация завершена!")
    
    def stop(self):
        if self.worker:
            self.worker.stop()
            self.stop_btn.setEnabled(False)
            self.log.append("Остановка генерации... Пожалуйста, подождите")

class DomainGeneratorApp(QMainWindow):
    def __init__(self):
        super().__init__()
        self.settings_manager = SettingsManager()
        self.app_settings = self.settings_manager.load()
        self.setWindowTitle("Генератор сайтов (Случайный подбор)")
        self.setWindowIcon(self.style().standardIcon(QStyle.SP_ComputerIcon))
        self.init_ui()
        
    def init_ui(self):
        central = QWidget()
        main_layout = QVBoxLayout(central)
        main_layout.setContentsMargins(5, 5, 5, 5)
        
        # Восстановление геометрии окна
        if self.app_settings.get('window_geometry'):
            self.restoreGeometry(self.app_settings['window_geometry'])
        
        # Установка флага "Поверх других окон"
        if self.app_settings.get('always_on_top', False):
            self.setWindowFlags(self.windowFlags() | Qt.WindowStaysOnTopHint)
        
        # Создаем панель инструментов в правом верхнем углу
        toolbar_layout = QHBoxLayout()
        toolbar_layout.addStretch()  # Добавляем растяжку слева
        
        # Кнопка настроек
        self.settings_btn = QPushButton()
        self.settings_btn.setIcon(QIcon.fromTheme(
            "preferences-system", 
            self.style().standardIcon(QStyle.SP_FileDialogDetailedView)
        ))
        self.settings_btn.setToolTip("Настройки")
        self.settings_btn.clicked.connect(self.open_settings)
        
        # Если иконка недоступна, показываем текст
        if self.settings_btn.icon().isNull():
            self.settings_btn.setText("Настройки")
        
        toolbar_layout.addWidget(self.settings_btn)
        main_layout.addLayout(toolbar_layout)
        
        # Создаем вкладки
        self.tabs = QTabWidget()
        
        # Вкладка генерации
        self.generator_tab = GeneratorTab()
        self.tabs.addTab(self.generator_tab, "Генератор")
        
        # Вкладка проверки
        self.checker_tab = CheckerTab()
        self.tabs.addTab(self.checker_tab, "Проверка дубликатов")
        
        main_layout.addWidget(self.tabs)
        self.setCentralWidget(central)
        
        # Устанавливаем начальный размер окна
        self.resize(800, 600)
        self.show()
    
    def open_settings(self):
        dialog = SettingsDialog(self.app_settings, self)
        
        if dialog.exec_() == QDialog.Accepted:
            new_settings = dialog.get_settings()
            
            # Обновляем настройки
            self.app_settings.update(new_settings)
            self.settings_manager.save(self.app_settings)
            
            # Применяем настройку "Поверх других окон"
            if self.app_settings['always_on_top']:
                self.setWindowFlags(self.windowFlags() | Qt.WindowStaysOnTopHint)
            else:
                self.setWindowFlags(self.windowFlags() & ~Qt.WindowStaysOnTopHint)
            
            # Перерисовываем окно
            self.show()
    
    def closeEvent(self, event):
        # Сохраняем геометрию окна
        self.app_settings['window_geometry'] = self.saveGeometry()
        self.settings_manager.save(self.app_settings)
        
        # Останавливаем генерацию, если она запущена
        if hasattr(self.generator_tab, 'worker') and self.generator_tab.worker:
            self.generator_tab.worker.stop()
            
            # Ждем завершения потока (макс 3 секунды)
            if not self.generator_tab.worker.wait(3000):
                self.generator_tab.worker.terminate()
        
        event.accept()

if __name__ == "__main__":
    # Глобальный обработчик исключений
    def handle_exception(exc_type, exc_value, exc_traceback):
        error_msg = ''.join(traceback.format_exception(exc_type, exc_value, exc_traceback))
        print(f"Необработанное исключение:\n{error_msg}")
        
        # Показываем сообщение об ошибке
        msg = QMessageBox()
        msg.setIcon(QMessageBox.Critical)
        msg.setText("Критическая ошибка")
        msg.setInformativeText(str(exc_value))
        msg.setWindowTitle("Ошибка приложения")
        msg.setDetailedText(error_msg)
        msg.exec_()
        
        # Завершаем приложение
        sys.exit(1)
    
    sys.excepthook = handle_exception
    
    # Фикс для Windows и asyncio
    if sys.platform == 'win32':
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
    
    app = QApplication(sys.argv)
    app.setStyle("Fusion")
    
    try:
        window = DomainGeneratorApp()
        window.show()
        sys.exit(app.exec_())
    except Exception as e:
        handle_exception(type(e), e, e.__traceback__)
