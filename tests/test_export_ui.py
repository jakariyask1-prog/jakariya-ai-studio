import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtWidgets import QApplication

from app.export.models import ExportFormatInfo
from app.ui import chat_area as chat_area_module
from app.ui.chat_area import ChatArea
from app.ui.header import Header


class ExportUiTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.application = QApplication.instance() or QApplication([])

    def test_header_lists_registered_export_formats_and_emits_selection(self):
        header = Header()
        selected_formats = []
        header.export_requested.connect(selected_formats.append)

        header.set_export_formats((
            ExportFormatInfo("pdf", "PDF document", ".pdf"),
            ExportFormatInfo("docx", "Word document", ".docx"),
        ))

        self.assertTrue(header.export_button.isEnabled())
        self.assertEqual([action.text() for action in header.export_menu.actions()], [
            "PDF document", "Word document"
        ])
        header.export_menu.actions()[1].trigger()
        self.assertEqual(selected_formats, ["docx"])

    def test_header_returns_the_selected_model_identifier(self):
        header = Header()

        header.model_selector.setCurrentIndex(1)

        expected_display_name = header.model_selector.itemText(1)
        expected_model_id = header.model_selector.itemData(1)
        self.assertEqual(header.model_selector.currentText(), expected_display_name)
        self.assertEqual(header.selected_model(), expected_model_id)

    def test_code_download_uses_fenced_language_extension_and_utf8_content(self):
        chat_area = ChatArea()
        with tempfile.TemporaryDirectory() as directory:
            destination = Path(directory) / "answer"
            with patch.object(
                chat_area_module.QFileDialog,
                "getSaveFileName",
                return_value=(str(destination), ""),
            ):
                chat_area._save_code_block("print('বাংলা')\n", "python")

            saved_file = destination.with_suffix(".py")
            self.assertEqual(saved_file.read_text(encoding="utf-8"), "print('বাংলা')\n")

    def test_extract_file_paths_resolves_relative_paths_to_existing_files(self):
        chat_area = ChatArea()
        with tempfile.TemporaryDirectory() as directory:
            relative_path = Path(directory) / "answer.txt"
            relative_path.write_text("test", encoding="utf-8")

            original_cwd = Path.cwd()
            try:
                os.chdir(directory)
                paths = chat_area._extract_file_paths("answer.txt")
                self.assertEqual(paths, [str(relative_path.resolve())])
            finally:
                os.chdir(original_cwd)


if __name__ == "__main__":
    unittest.main()
