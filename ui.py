import sys
import traceback
import os
from pathlib import Path

from PyQt6.QtCore import QMutex, QThread, QWaitCondition, pyqtSignal
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
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from main import run_processing


class ProcessingWorker(QThread):
    completed = pyqtSignal()
    failed = pyqtSignal(str)
    mapping_review_requested = pyqtSignal(str, dict, list)

    def __init__(self, paths):
        super().__init__()
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
            run_processing(**self.paths, mapping_reviewer=self.review_mappings)
        except Exception:
            self.failed.emit(traceback.format_exc())
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
        self.setWindowTitle('Buzzly Data Processor')
        self.setMinimumWidth(720)

        central_widget = QWidget()
        layout = QVBoxLayout(central_widget)
        layout.setSpacing(16)
        layout.setContentsMargins(28, 28, 28, 28)

        title = QLabel('Buzzly Data Processor')
        title.setObjectName('title')
        subtitle = QLabel('Select source data and choose where processed CSV files will be written.')
        subtitle.setWordWrap(True)
        layout.addWidget(title)
        layout.addWidget(subtitle)

        required_section = self.create_section('Required source data')
        required_form = QFormLayout(required_section)
        required_form.setSpacing(12)
        self.challenges = PathSelector('Challenges')
        self.sponsors = PathSelector('Sponsors')
        self.users = PathSelector('Users')
        required_form.addRow('challenges.csv', self.challenges)
        required_form.addRow('sponsors.csv', self.sponsors)
        required_form.addRow('users.csv', self.users)
        layout.addWidget(required_section)

        optional_section = self.create_section('Optional geospatial data')
        optional_form = QFormLayout(optional_section)
        optional_form.setSpacing(12)
        self.postcodes = PathSelector('Postcode boundaries', required=False)
        self.regions = PathSelector('Regional councils', required=False)
        optional_form.addRow('postcode_boundaries.zip', self.postcodes)
        optional_form.addRow('regional_councils.zip', self.regions)
        layout.addWidget(optional_section)

        output_section = self.create_section('Output')
        output_form = QFormLayout(output_section)
        self.output = PathSelector('Output folder', directory=True)
        output_form.addRow('Processed CSV folder', self.output)
        layout.addWidget(output_section)

        ai_section = self.create_section('AI settings')
        ai_form = QFormLayout(ai_section)
        # import AI model options from config.json
        import json
        with open('config.json', 'r') as f:
            config = json.load(f)
        ai_options = config.get('AI_MODEL_SUPPORT', [])
        self.primary_ai_model = QComboBox()
        self.primary_ai_model.setEditable(True)
        self.primary_ai_model.addItems(ai_options)
        self.primary_ai_model.setToolTip('Generates mappings and the data summary. Enter any model installed in Ollama.')
        self.secondary_ai_model = QComboBox()
        self.secondary_ai_model.setEditable(True)
        self.secondary_ai_model.addItems(ai_options)
        self.secondary_ai_model.setToolTip('Verifies generated mappings and corrects invalid JSON responses.')
        ai_form.addRow('Primary Ollama model', self.primary_ai_model)
        ai_form.addRow('Secondary Ollama model', self.secondary_ai_model)
        layout.addWidget(ai_section)

        self.status = QLabel('Ready to process data.')
        self.status.setObjectName('status')
        self.process_button = QPushButton('Process data')
        self.process_button.clicked.connect(self.process_data)
        layout.addWidget(self.status)
        layout.addWidget(self.process_button)
        layout.addStretch()

        self.setCentralWidget(central_widget)
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

    def process_data(self):
        required_paths = [self.challenges.value(), self.sponsors.value(), self.users.value(), self.output.value()]
        if not all(required_paths):
            QMessageBox.warning(self, 'Missing paths', 'Select all required CSV files and an output folder.')
            return

        invalid_paths = [path for path in required_paths[:3] if not Path(path).is_file()]
        optional_paths = [path for path in [self.postcodes.value(), self.regions.value()] if path]
        invalid_paths.extend(path for path in optional_paths if not Path(path).is_file())
        if invalid_paths:
            QMessageBox.warning(self, 'Invalid path', f'These selected files do not exist:\n' + '\n'.join(invalid_paths))
            return
        if not self.primary_ai_model.currentText().strip() or not self.secondary_ai_model.currentText().strip():
            QMessageBox.warning(self, 'Missing AI model', 'Enter both a primary and secondary Ollama model.')
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

        self.process_button.setEnabled(False)
        self.status.setText('Processing data. This may take a few minutes while mappings are generated.')
        self.worker = ProcessingWorker({
            'challenges_file': self.challenges.value(),
            'sponsors_file': self.sponsors.value(),
            'users_file': self.users.value(),
            'output_directory': self.output.value(),
            'geodata_file': self.postcodes.value() or None,
            'regional_geodata_file': self.regions.value() or None,
            'primary_ai_model': self.primary_ai_model.currentText().strip(),
            'secondary_ai_model': self.secondary_ai_model.currentText().strip(),
        })
        self.worker.completed.connect(self.processing_completed)
        self.worker.failed.connect(self.processing_failed)
        self.worker.mapping_review_requested.connect(self.review_mappings)
        self.worker.start()

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
        QMessageBox.critical(self, 'Processing failed', error)


def main():
    app = QApplication(sys.argv)
    window = BuzzlyWindow()
    window.show()
    sys.exit(app.exec())


if __name__ == '__main__':
    main()