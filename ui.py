import sys
import traceback
import os
from contextlib import redirect_stdout
from pathlib import Path

from PyQt6.QtCore import QMutex, QSettings, QThread, QWaitCondition, pyqtSignal
from PyQt6.QtGui import QTextCursor
from PyQt6.QtWidgets import (
    QApplication,
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QFileDialog,
    QFormLayout,
    QFrame,
    QHBoxLayout,
    QInputDialog,
    QLabel,
    QLineEdit,
    QMainWindow,
    QMessageBox,
    QPushButton,
    QScrollArea,
    QTableWidget,
    QTableWidgetItem,
    QTextEdit,
    QTabWidget,
    QVBoxLayout,
    QWidget,
)

from main import run_processing
from sub_processes.ai_call import gemini_check_api_key, get_stored_gemini_api_key, store_gemini_api_key
from sub_processes.process_individual_challenge import process_from_beginning


class ProgressOutput:
    def __init__(self, write_callback):
        self.write_callback = write_callback

    def write(self, message):
        if message:
            self.write_callback(message)

    def flush(self):
        pass


class ProcessingWorker(QThread):
    completed = pyqtSignal()
    failed = pyqtSignal(str)
    mapping_review_requested = pyqtSignal(str, dict, list)
    progress_updated = pyqtSignal(str)

    def __init__(self, processor, paths):
        super().__init__()
        self.processor = processor
        self.paths = paths
        self.review_mutex = QMutex()
        self.review_complete = QWaitCondition()
        self.reviewed_values = None

    def review_mappings(self, mapping_type, values, categories):
        self.review_mutex.lock()
        self.reviewed_values = None
        self.mapping_review_requested.emit(mapping_type, values, categories)
        self.review_complete.wait(self.review_mutex)
        reviewed_values = self.reviewed_values
        self.review_mutex.unlock()
        return reviewed_values

    def submit_review(self, values):
        self.review_mutex.lock()
        self.reviewed_values = values
        self.review_complete.wakeAll()
        self.review_mutex.unlock()

    def run(self):
        try:
            with redirect_stdout(ProgressOutput(self.progress_updated.emit)):
                self.processor(**self.paths, mapping_reviewer=self.review_mappings)
        except Exception:
            error = traceback.format_exc()
            self.progress_updated.emit(error)
            self.failed.emit(error)
        else:
            self.completed.emit()


class PathSelector(QWidget):
    def __init__(self, label, required=True, directory=False, parent=None):
        super().__init__(parent)
        self.directory = directory
        self.required = required
        self.path_input = QLineEdit()
        self.path_input.setPlaceholderText('Required' if required else 'Optional')
        self.browse_button = QPushButton('Browse...')
        self.browse_button.clicked.connect(self.select_path)

        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(self.path_input)
        layout.addWidget(self.browse_button)

    def select_path(self):
        if self.directory:
            selected = QFileDialog.getExistingDirectory(self, 'Choose output folder')
        else:
            selected, _ = QFileDialog.getOpenFileName(
                self,
                'Choose file',
                '',
                'CSV files (*.csv);;ZIP archives (*.zip);;All files (*)',
            )
        if selected:
            self.path_input.setText(selected)

    def value(self):
        return self.path_input.text().strip()


class MappingReviewDialog(QDialog):
    def __init__(self, mapping_type, values, categories, parent=None):
        super().__init__(parent)
        self.setWindowTitle(f'Review New {mapping_type} Mappings')
        self.setMinimumWidth(560)
        layout = QVBoxLayout(self)
        message = QLabel(f'Review the new {mapping_type.lower()} values before they are saved.')
        message.setWordWrap(True)
        layout.addWidget(message)

        self.table = QTableWidget(len(values), 2)
        self.table.setHorizontalHeaderLabels(['Raw value', 'Category'])
        self.table.verticalHeader().setVisible(False)
        self.table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.table.setColumnWidth(0, 275)
        self.table.horizontalHeader().setStretchLastSection(True)
        for row, raw_value in enumerate(sorted(values, key=str.casefold)):
            self.table.setItem(row, 0, QTableWidgetItem(raw_value))
            category = QComboBox()
            category.addItems(categories)
            category.setCurrentText(values[raw_value])
            self.table.setCellWidget(row, 1, category)
        layout.addWidget(self.table)

        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Save | QDialogButtonBox.StandardButton.Cancel)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

    def reviewed_values(self):
        return {
            self.table.item(row, 0).text(): self.table.cellWidget(row, 1).currentText()
            for row in range(self.table.rowCount())
        }


class BuzzlyWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.worker = None
        self.settings = QSettings('Buzzly', 'Data Processor')
        try:
            stored_gemini_api_key = get_stored_gemini_api_key()
        except Exception:
            stored_gemini_api_key = None
        if stored_gemini_api_key:
            os.environ['GEMINI_API_KEY'] = stored_gemini_api_key
        self.setWindowTitle('Buzzly Data Processor')
        self.setMinimumWidth(980)

        processing_widget = QWidget()
        layout = QVBoxLayout(processing_widget)
        layout.setSpacing(16)
        layout.setContentsMargins(28, 28, 28, 28)

        title = QLabel('Buzzly Data Processor')
        title.setObjectName('title')
        subtitle = QLabel('Select source data and choose where processed CSV files will be written.')
        subtitle.setWordWrap(True)
        layout.addWidget(title)
        layout.addWidget(subtitle)

        content_layout = QHBoxLayout()
        content_layout.setSpacing(16)
        layout.addLayout(content_layout, 1)
        controls_layout = QVBoxLayout()
        content_layout.addLayout(controls_layout, 3)

        required_section = self.create_section('Required source data')
        required_form = QFormLayout(required_section)
        required_form.setSpacing(12)
        self.challenges = PathSelector('Challenges')
        self.sponsors = PathSelector('Sponsors')
        self.users = PathSelector('Users')
        self.submissions = PathSelector('Submissions')
        required_form.addRow('challenges.csv', self.challenges)
        required_form.addRow('sponsors.csv', self.sponsors)
        required_form.addRow('users.csv', self.users)
        required_form.addRow('submissions.csv', self.submissions)
        controls_layout.addWidget(required_section)

        optional_section = self.create_section('Optional geospatial data')
        optional_form = QFormLayout(optional_section)
        optional_form.setSpacing(12)
        self.postcodes = PathSelector('Postcode boundaries', required=False)
        self.regions = PathSelector('Regional councils', required=False)
        optional_form.addRow('postcode_boundaries.zip', self.postcodes)
        optional_form.addRow('regional_councils.zip', self.regions)
        controls_layout.addWidget(optional_section)

        output_section = self.create_section('Output')
        output_form = QFormLayout(output_section)
        self.output = PathSelector('Output folder', directory=True)
        output_form.addRow('Processed CSV folder', self.output)
        controls_layout.addWidget(output_section)

        finances_section = self.create_section('Financial information')
        finances_form = QFormLayout(finances_section)
        self.monthly_expenses = QLineEdit()
        self.monthly_income = QLineEdit()
        self.ytd_expenses = QLineEdit()
        self.ytd_income = QLineEdit()
        finances_form.addRow('Monthly expenses', self.monthly_expenses)
        finances_form.addRow('Monthly income', self.monthly_income)
        finances_form.addRow('YTD expenses', self.ytd_expenses)
        finances_form.addRow('YTD income', self.ytd_income)
        controls_layout.addWidget(finances_section)

        ai_section = self.create_section('AI settings')
        ai_form = QFormLayout(ai_section)
        # import AI model options from config.json
        import json
        with open('config.json', 'r') as f:
            config = json.load(f)
        self.ai_options = config.get('AI_MODEL_SUPPORT', [])
        self.primary_ai_model = QComboBox()
        self.primary_ai_model.setEditable(True)
        self.primary_ai_model.addItems(self.ai_options)
        self.primary_ai_model.setToolTip('Generates mappings and the data summary. Enter any model installed in Ollama.')
        self.secondary_ai_model = QComboBox()
        self.secondary_ai_model.setEditable(True)
        self.secondary_ai_model.addItems(self.ai_options)
        self.secondary_ai_model.setToolTip('Verifies generated mappings and corrects invalid JSON responses.')
        ai_form.addRow('Primary Ollama model', self.primary_ai_model)
        ai_form.addRow('Secondary Ollama model', self.secondary_ai_model)
        controls_layout.addWidget(ai_section)
        self.restore_preferences()
        self.connect_preference_signals()

        self.status = QLabel('Ready to process data.')
        self.status.setObjectName('status')
        self.process_button = QPushButton('Process data')
        self.process_button.clicked.connect(self.process_data)
        self.progress_log = QTextEdit()
        self.progress_log.setReadOnly(True)
        self.progress_log.setPlaceholderText('Processing updates will appear here.')
        self.progress_log.setMinimumHeight(180)
        controls_layout.addWidget(self.status)
        controls_layout.addWidget(self.process_button)
        controls_layout.addStretch()

        progress_layout = QVBoxLayout()
        progress_layout.addWidget(QLabel('Processing progress'))
        progress_layout.addWidget(self.progress_log, 1)
        content_layout.addLayout(progress_layout, 2)

        tabs = QTabWidget()
        tabs.addTab(processing_widget, 'Process all data')
        tabs.addTab(self.create_individual_challenge_tab(), 'Process individual challenge')
        scroll_area = QScrollArea()
        scroll_area.setWidgetResizable(True)
        scroll_area.setFrameShape(QFrame.Shape.NoFrame)
        scroll_area.setWidget(tabs)
        self.setCentralWidget(scroll_area)
        self.setStyleSheet(
            'QMainWindow { background: #f6f7f4; }'
            'QLabel { color: #25332b; font-size: 14px; }'
            'QLabel#title { font-size: 26px; font-weight: 700; }'
            'QLabel#status { color: #456052; }'
            'QFrame { background: white; border: 1px solid #d7ddd7; border-radius: 6px; }'
            'QLineEdit { padding: 8px; border: 1px solid #b7c3b9; border-radius: 4px; background: #fff; }'
            'QPushButton { padding: 9px 14px; background: #146c43; color: white; border: none; border-radius: 4px; font-weight: 600; }'
            'QPushButton:hover { background: #0e5735; }'
            'QPushButton:disabled { background: #aeb8b0; }'
        )

    @staticmethod
    def create_section(title):
        section = QFrame()
        section.setObjectName(title)
        return section

    def create_individual_challenge_tab(self):
        tab = QWidget()
        layout = QVBoxLayout(tab)
        layout.setSpacing(16)
        layout.setContentsMargins(28, 28, 28, 28)

        title = QLabel('Individual Challenge Processor')
        title.setObjectName('title')
        layout.addWidget(title)
        layout.addWidget(QLabel('Process and anonymise one challenge CSV file.'))

        input_section = self.create_section('Input')
        input_form = QFormLayout(input_section)
        self.individual_challenge = PathSelector('Challenge file')
        input_form.addRow('Challenge CSV file', self.individual_challenge)
        layout.addWidget(input_section)

        output_section = self.create_section('Output')
        output_form = QFormLayout(output_section)
        self.individual_output = PathSelector('Output folder', directory=True)
        output_form.addRow('Output folder', self.individual_output)
        layout.addWidget(output_section)

        ai_section = self.create_section('AI settings')
        ai_form = QFormLayout(ai_section)
        self.individual_primary_ai_model = QComboBox()
        self.individual_primary_ai_model.setEditable(True)
        self.individual_primary_ai_model.addItems(self.ai_options)
        self.individual_secondary_ai_model = QComboBox()
        self.individual_secondary_ai_model.setEditable(True)
        self.individual_secondary_ai_model.addItems(self.ai_options)
        ai_form.addRow('Primary AI model', self.individual_primary_ai_model)
        ai_form.addRow('Secondary AI model', self.individual_secondary_ai_model)
        layout.addWidget(ai_section)

        self.individual_status = QLabel('Ready to process an individual challenge.')
        self.individual_status.setObjectName('status')
        self.individual_process_button = QPushButton('Process individual challenge')
        self.individual_process_button.clicked.connect(self.process_individual_challenge)
        layout.addWidget(self.individual_status)
        layout.addWidget(self.individual_process_button)
        layout.addStretch()
        return tab

    def restore_preferences(self):
        for setting_name, selector in self.preference_path_selectors().items():
            selector.path_input.setText(str(self.settings.value(setting_name, '')))
        self.primary_ai_model.setCurrentText(str(self.settings.value('primary_ai_model', self.primary_ai_model.currentText())))
        self.secondary_ai_model.setCurrentText(str(self.settings.value('secondary_ai_model', self.secondary_ai_model.currentText())))

    def connect_preference_signals(self):
        for selector in self.preference_path_selectors().values():
            selector.path_input.textChanged.connect(self.save_preferences)
        self.primary_ai_model.currentTextChanged.connect(self.save_preferences)
        self.secondary_ai_model.currentTextChanged.connect(self.save_preferences)

    def preference_path_selectors(self):
        return {
            'challenges_file': self.challenges,
            'sponsors_file': self.sponsors,
            'users_file': self.users,
            'submissions_file': self.submissions,
            'postcode_file': self.postcodes,
            'regions_file': self.regions,
            'output_directory': self.output,
        }

    def save_preferences(self):
        for setting_name, selector in self.preference_path_selectors().items():
            self.settings.setValue(setting_name, selector.value())
        self.settings.setValue('primary_ai_model', self.primary_ai_model.currentText().strip())
        self.settings.setValue('secondary_ai_model', self.secondary_ai_model.currentText().strip())

    def process_data(self):
        required_paths = [self.challenges.value(), self.sponsors.value(), self.users.value(), self.submissions.value(), self.output.value()]
        if not all(required_paths):
            QMessageBox.warning(self, 'Missing paths', 'Select all required CSV files and an output folder.')
            return

        invalid_paths = [path for path in required_paths[:4] if not Path(path).is_file()]
        optional_paths = [path for path in [self.postcodes.value(), self.regions.value()] if path]
        invalid_paths.extend(path for path in optional_paths if not Path(path).is_file())
        if invalid_paths:
            QMessageBox.warning(self, 'Invalid path', f'These selected files do not exist:\n' + '\n'.join(invalid_paths))
            return
        if not self.primary_ai_model.currentText().strip() or not self.secondary_ai_model.currentText().strip():
            QMessageBox.warning(self, 'Missing AI model', 'Enter both a primary and secondary AI model.')
            return

        finances_fields = {
            'monthly_expenses': self.monthly_expenses.text().strip(),
            'monthly_income': self.monthly_income.text().strip(),
            'ytd_expenses': self.ytd_expenses.text().strip(),
            'ytd_income': self.ytd_income.text().strip(),
        }
        if not all(finances_fields.values()):
            QMessageBox.warning(self, 'Missing financial information', 'Enter monthly and YTD expenses and income.')
            return

        selected_models = [self.primary_ai_model.currentText().strip(), self.secondary_ai_model.currentText().strip()]
        if any(model.startswith('gpt:') for model in selected_models) and not os.environ.get('OPENAI_API_KEY'):
            api_key, accepted = QInputDialog.getText(
                self,
                'OpenAI API Key',
                'Enter your OpenAI API key:',
                QLineEdit.EchoMode.Password,
            )
            if not accepted or not api_key.strip():
                return
            os.environ['OPENAI_API_KEY'] = api_key.strip()

        if any(model.startswith('gemini:') for model in selected_models) and not os.environ.get('GEMINI_API_KEY'):
            api_key, accepted = QInputDialog.getText(
                self,
                'Gemini API Key',
                'Enter your Gemini API key:',
                QLineEdit.EchoMode.Password,
            )
            if not accepted or not api_key.strip():
                return
            try:
                gemini_check_api_key(api_key.strip())
            except Exception as error:
                QMessageBox.warning(self, 'Invalid Gemini API Key', f'Gemini could not validate this API key:\n{error}')
                return
            try:
                store_gemini_api_key(api_key.strip())
            except Exception as error:
                QMessageBox.warning(self, 'Gemini API Key Not Saved', f'Gemini accepted this API key, but it could not be saved securely:\n{error}')
                return
            os.environ['GEMINI_API_KEY'] = api_key.strip()

        self.process_button.setEnabled(False)
        self.status.setText('Processing data. This may take a few minutes while mappings are generated.')
        self.progress_log.clear()
        self.worker = ProcessingWorker(run_processing, {
            'challenges_file': self.challenges.value(),
            'sponsors_file': self.sponsors.value(),
            'users_file': self.users.value(),
            'submissions_file': self.submissions.value(),
            'output_directory': self.output.value(),
            'geodata_file': self.postcodes.value() or None,
            'regional_geodata_file': self.regions.value() or None,
            'primary_ai_model': self.primary_ai_model.currentText().strip(),
            'secondary_ai_model': self.secondary_ai_model.currentText().strip(),
            'finances_data': finances_fields,
        })
        self.worker.completed.connect(self.processing_completed)
        self.worker.failed.connect(self.processing_failed)
        self.worker.mapping_review_requested.connect(self.review_mappings)
        self.worker.progress_updated.connect(self.append_progress)
        self.worker.start()

    def process_individual_challenge(self):
        challenge_file = self.individual_challenge.value()
        output_directory = self.individual_output.value()
        primary_ai_model = self.individual_primary_ai_model.currentText().strip()
        secondary_ai_model = self.individual_secondary_ai_model.currentText().strip()
        if not all([challenge_file, output_directory, primary_ai_model, secondary_ai_model]):
            QMessageBox.warning(self, 'Missing information', 'Select a challenge CSV file and output folder, then enter both AI models.')
            return
        if not Path(challenge_file).is_file():
            QMessageBox.warning(self, 'Invalid path', 'The selected challenge CSV file does not exist.')
            return

        self.individual_process_button.setEnabled(False)
        self.individual_status.setText('Processing individual challenge.')
        self.progress_log.clear()
        self.worker = ProcessingWorker(process_from_beginning, {
            'challenge_file': challenge_file,
            'output_dir': output_directory,
            'primary_ai_model': primary_ai_model,
            'secondary_ai_model': secondary_ai_model,
        })
        self.worker.completed.connect(self.individual_processing_completed)
        self.worker.failed.connect(self.individual_processing_failed)
        self.worker.mapping_review_requested.connect(self.review_mappings)
        self.worker.progress_updated.connect(self.append_progress)
        self.worker.start()

    def append_progress(self, message):
        self.progress_log.moveCursor(QTextCursor.MoveOperation.End)
        self.progress_log.insertPlainText(message)
        self.progress_log.ensureCursorVisible()

    def review_mappings(self, mapping_type, values, categories):
        dialog = MappingReviewDialog(mapping_type, values, categories, self)
        if dialog.exec() == QDialog.DialogCode.Accepted:
            self.worker.submit_review(dialog.reviewed_values())
        else:
            self.worker.submit_review(None)

    def processing_completed(self):
        self.process_button.setEnabled(True)
        self.status.setText('Processing complete.')
        QMessageBox.information(self, 'Complete', f'Processed CSV files were written to:\n{self.output.value()}')

    def processing_failed(self, error):
        self.process_button.setEnabled(True)
        self.status.setText('Processing failed.')
        print(error)
        QMessageBox.critical(self, 'Processing failed', error)

    def individual_processing_completed(self):
        self.individual_process_button.setEnabled(True)
        self.individual_status.setText('Individual challenge processing complete.')
        QMessageBox.information(self, 'Complete', f'Processed challenge CSV was written to:\n{self.individual_output.value()}')

    def individual_processing_failed(self, error):
        self.individual_process_button.setEnabled(True)
        self.individual_status.setText('Individual challenge processing failed.')
        print(error)
        QMessageBox.critical(self, 'Processing failed', error)


def main():
    app = QApplication(sys.argv)
    window = BuzzlyWindow()
    window.show()
    sys.exit(app.exec())


if __name__ == '__main__':
    main()