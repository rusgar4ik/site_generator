import sys, os, asyncio, aiohttp, aiodns, string, ssl, random
from PyQt5.QtWidgets import (QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, 
                             QLabel, QLineEdit, QPushButton, QProgressBar, QTextEdit, QSpinBox, 
                             QFileDialog, QMessageBox, QGroupBox, QSplitter, QFrame, QTabWidget)
from PyQt5.QtCore import Qt, QThread, pyqtSignal, QMutex, QTimer
from PyQt5.QtGui import QFont, QColor, QTextCharFormat, QPainter, QBrush, QLinearGradient

class GradientWidget(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.timer = QTimer(self)
        self.timer.timeout.connect(self.update)
        self.timer.start(50)
        self.hue = 0
        self.offset = 0
        self.setMinimumSize(200, 200)
        self.setAttribute(Qt.WA_TransparentForMouseEvents)
        
    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        
        gradient = QLinearGradient(0, 0, self.width(), self.height())
        
        self.hue = (self.hue + 0.5) % 360
        self.offset = (self.offset + 1) % 100
        
        color1 = QColor.fromHsv(int(self.hue) % 360, 255, 255)
        color2 = QColor.fromHsv(int(self.hue + 120) % 360, 255, 200)
        color3 = QColor.fromHsv(int(self.hue + 240) % 360, 255, 150)
        
        pos1 = (0 + self.offset) / 100
        pos2 = (33 + self.offset) / 100
        pos3 = (66 + self.offset) / 100
        
        gradient.setColorAt(max(0, min(1, pos1)), color1)
        gradient.setColorAt(max(0, min(1, pos2)), color2)
        gradient.setColorAt(max(0, min(1, pos3)), color3)
        
        painter.fillRect(self.rect(), QBrush(gradient))

class DomainGenerator(QThread):
    update_progress = pyqtSignal(int, int)
    update_log = pyqtSignal(str)
    update_stats = pyqtSignal(str)
    found_site = pyqtSignal(str)
    finished = pyqtSignal()
    
    def __init__(self, min_length, max_length, output_file):
        super().__init__()
        self.min_length, self.max_length = min_length, max_length
        self.output_file, self.running = output_file, True
        self.checked_count, self.valid_count = 0, 0
        self.chars = string.ascii_lowercase + string.digits
        self.tlds = ['.com', '.org', '.net']
        self.file_mutex = QMutex()
        self.loop = None
        self.max_workers = 500
        self.batch_size = 5000
        self.dns_batch_size = 100
        self.resolver = None
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
            result = await self.resolver.query(domain, 'A')
            if result:
                return True, f"DNS найден: {domain}"
            return False, f"DNS не найден: {domain}"
        except aiodns.error.DNSError as e:
            if e.args[0] == 4:
                return False, f"DNS домен не существует: {domain}"
            return False, f"DNS ошибка для {domain}: {str(e)}"
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
        
        for domain in domains:
            if not self.running:
                break
                
            dns_ok, dns_log = await self.check_dns(domain)
            self.update_log.emit(dns_log)
            
            if not dns_ok:
                continue
                
            http_ok, http_log = await self.check_http(session, domain)
            self.update_log.emit(http_log)
            
            if http_ok:
                working_count += 1
        
        self.checked_count += len(domains)
        self.update_progress.emit(self.checked_count, self.total_domains)
        self.update_stats.emit(f"Проверено: {self.checked_count}/{self.total_domains} | Рабочих: {self.valid_count}")
    
    async def run_async(self):
        self.resolver = aiodns.DNSResolver()
        self.resolver.nameservers = ['8.8.8.8', '1.1.1.1', '9.9.9.9', '1.0.0.1']
        
        try:
            await self.resolver.query("google.com", "A")
            self.update_log.emit("DNS проверка: google.com разрешен успешно")
        except Exception as e:
            self.update_log.emit(f"Ошибка DNS: {str(e)}")
            return
        
        async with aiohttp.ClientSession(
            connector=aiohttp.TCPConnector(limit_per_host=50, ssl=False),
            headers={"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36"}
        ) as session:
            
            test_ok, test_log = await self.check_http(session, "google.com")
            self.update_log.emit(f"Тест HTTP: {test_log}")
            
            if not test_ok:
                self.update_log.emit("Проверка сети: Google недоступен, проверьте интернет-соединение")
                return
            
            sem = asyncio.Semaphore(self.max_workers)
            tasks = []
            
            while self.running and self.checked_count < self.total_domains:
                domains = self.generate_domains_batch(self.batch_size)
                
                await sem.acquire()
                task = asyncio.create_task(self.process_domains(session, domains))
                task.add_done_callback(lambda _: sem.release())
                tasks.append(task)
            
            await asyncio.gather(*tasks)
    
    def run(self):
        try:
            self.loop = asyncio.new_event_loop()
            asyncio.set_event_loop(self.loop)
            self.loop.run_until_complete(self.run_async())
            self.update_log.emit(f"Завершено! Рабочих сайтов: {self.valid_count}")
        except asyncio.CancelledError:
            self.update_log.emit("Генерация отменена пользователем")
        except Exception as e: 
            import traceback
            self.update_log.emit(f"Критическая ошибка: {str(e)}\n{traceback.format_exc()}")
        finally: 
            self.finished.emit()
    
    def stop(self):
        self.running = False
        if self.loop:
            for task in asyncio.all_tasks(self.loop):
                task.cancel()
            self.update_log.emit("Задачи отменены, ожидание завершения...")

class CheckerTab(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.init_ui()
        
    def init_ui(self):
        layout = QVBoxLayout()
        layout.setContentsMargins(10, 10, 10, 10)
        
        # Группа выбора файла
        file_group = QGroupBox("Файл с сайтами")
        file_layout = QVBoxLayout()
        
        file_select_layout = QHBoxLayout()
        file_select_layout.addWidget(QLabel("Файл результатов:"))
        self.file_edit = QLineEdit("sites.txt")
        file_select_layout.addWidget(self.file_edit)
        self.browse_btn = QPushButton("Обзор")
        self.browse_btn.clicked.connect(self.browse_file)
        file_select_layout.addWidget(self.browse_btn)
        
        file_layout.addLayout(file_select_layout)
        file_group.setLayout(file_layout)
        layout.addWidget(file_group)
        
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
        
        self.clear_btn = QPushButton("Очистить файл")
        self.clear_btn.clicked.connect(self.clear_file)
        btn_layout.addWidget(self.clear_btn)
        
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
    
    def browse_file(self):
        filename, _ = QFileDialog.getOpenFileName(
            self, 
            "Выберите файл с сайтами", 
            "", 
            "Текстовые файлы (*.txt)"
        )
        if filename:
            self.file_edit.setText(filename)
    
    def clear_file(self):
        filename = self.file_edit.text()
        if not filename:
            return
            
        try:
            with open(filename, 'w') as f:
                f.write("")
            self.log.append(f"Файл {filename} успешно очищен")
        except Exception as e:
            self.log.append(f"Ошибка при очистке файла: {str(e)}")
    
    def check_duplicates(self):
        filename = self.file_edit.text()
        if not filename or not os.path.exists(filename):
            self.log.append("Файл не найден!")
            return
            
        try:
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
        filename = self.file_edit.text()
        if not filename or not os.path.exists(filename):
            return
            
        try:
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
        
        file_layout = QHBoxLayout()
        file_layout.addWidget(QLabel("Файл результатов:"))
        self.file_edit = QLineEdit("sites.txt")
        file_layout.addWidget(self.file_edit)
        self.browse_btn = QPushButton("Обзор")
        self.browse_btn.clicked.connect(self.browse_file)
        file_layout.addWidget(self.browse_btn)
        
        self.clear_btn = QPushButton("Очистить файл")
        self.clear_btn.clicked.connect(self.clear_file)
        file_layout.addWidget(self.clear_btn)
        
        settings_layout.addLayout(file_layout)
        
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
    
    def browse_file(self):
        filename, _ = QFileDialog.getSaveFileName(
            self, 
            "Сохранить файл", 
            "", 
            "Текстовые файлы (*.txt)"
        )
        if filename:
            self.file_edit.setText(filename)
    
    def clear_file(self):
        filename = self.file_edit.text()
        if not filename:
            return
            
        try:
            with open(filename, 'w') as f:
                f.write("")
            self.log.append(f"Файл {filename} очищен")
        except Exception as e:
            self.log.append(f"Ошибка при очистке файла: {str(e)}")
    
    def start(self):
        min_len = self.min_spin.value()
        max_len = self.max_spin.value()
        file = self.file_edit.text()
        
        if min_len > max_len:
            QMessageBox.critical(self, "Ошибка", "Минимальная длина не может быть больше максимальной")
            return
            
        if min_len < 1 or max_len > 5:
            QMessageBox.critical(self, "Ошибка", "Длина домена должна быть от 1 до 5 символов")
            return
            
        if not file: 
            QMessageBox.critical(self, "Ошибка", "Укажите файл для сохранения результатов")
            return
        
        self.log.clear()
        self.start_btn.setEnabled(False)
        self.stop_btn.setEnabled(True)
        self.progress.setValue(0)
        self.log.append("Запуск случайной генерации доменов...")
        self.log.append(f"Диапазон длины: {min_len}-{max_len} символов")
        self.log.append(f"Доменные зоны: .com, .org, .net")
        
        if not os.path.exists(file):
            with open(file, 'w') as f:
                self.log.append(f"Создан новый файл: {file}")
        
        chars_count = len(string.ascii_lowercase + string.digits)
        total = 0
        for length in range(min_len, max_len + 1):
            total += (chars_count ** length) * 3
        self.log.append(f"Всего возможных доменов: {total:,}")
        
        self.worker = DomainGenerator(min_len, max_len, file)
        self.worker.update_progress.connect(self.update_progress)
        self.worker.update_log.connect(self.log.append)
        self.worker.update_stats.connect(self.status.setText)
        self.worker.found_site.connect(self.highlight_found_site)
        self.worker.finished.connect(self.task_finished)
        self.worker.start()
    
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
        format.setFontWeight(75)
        
        cursor.insertText(f"✓ Рабочий сайт: {domain}\n", format)
        self.log.ensureCursorVisible()
    
    def task_finished(self):
        self.start_btn.setEnabled(True)
        self.stop_btn.setEnabled(False)
        self.log.append("Генерация завершена!")
    
    def stop(self):
        if hasattr(self, 'worker'):
            self.worker.stop()
            self.stop_btn.setEnabled(False)
            self.log.append("Остановка генерации... Пожалуйста, подождите")

class DomainGeneratorApp(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Генератор сайтов (Случайный подбор)")
        self.init_ui()
        
    def init_ui(self):
        central = QWidget()
        main_layout = QHBoxLayout(central)
        main_layout.setContentsMargins(5, 5, 5, 5)
        
        # Создаем вкладки
        self.tabs = QTabWidget()
        
        # Вкладка генерации
        self.generator_tab = GeneratorTab()
        self.tabs.addTab(self.generator_tab, "Генератор")
        
        # Вкладка проверки
        self.checker_tab = CheckerTab()
        self.tabs.addTab(self.checker_tab, "Проверка")
        
        # Градиентная панель
        gradient_frame = QFrame()
        gradient_layout = QVBoxLayout(gradient_frame)
        self.gradient_widget = GradientWidget()
        gradient_layout.addWidget(self.gradient_widget)
        
        # Разделитель
        splitter = QSplitter(Qt.Horizontal)
        splitter.addWidget(self.tabs)
        splitter.addWidget(gradient_frame)
        splitter.setSizes([700, 300])
        
        main_layout.addWidget(splitter)
        self.setCentralWidget(central)
        
        # Устанавливаем размер окна и показываем его
        self.resize(1200, 700)
        self.show()

if __name__ == "__main__":
    app = QApplication(sys.argv)
    app.setStyle("Fusion")
    
    window = DomainGeneratorApp()
    window.show()
    sys.exit(app.exec_())
