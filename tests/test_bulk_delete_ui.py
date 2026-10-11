import unittest
from PySide6.QtWidgets import QApplication
from app.models.conversation import Conversation
from app.ui.sidebar import Sidebar
from app.ui.widgets.conversation_item import ConversationItem

app = QApplication.instance() or QApplication([])


class TestBulkDeleteUI(unittest.TestCase):
    def setUp(self):
        self.sidebar = Sidebar()
        self.conversations = [
            Conversation("c1", "First Chat", "2026-08-01T00:00:00", "2026-08-01T00:00:00"),
            Conversation("c2", "Second Chat", "2026-08-01T00:00:00", "2026-08-01T00:00:00"),
            Conversation("c3", "Third Chat", "2026-08-01T00:00:00", "2026-08-01T00:00:00"),
        ]
        self.sidebar.set_conversations(self.conversations, active_conversation_id="c1")

    def test_toggle_check_mode_shows_checkboxes(self):
        self.sidebar.toggle_check_mode(True)
        self.assertTrue(self.sidebar._is_check_mode)
        self.assertFalse(self.sidebar.bulk_bar.isHidden())

        # Check all items in list
        for i in range(self.sidebar.chat_list.count()):
            item = self.sidebar.chat_list.item(i)
            widget = self.sidebar.chat_list.itemWidget(item)
            self.assertIsInstance(widget, ConversationItem)
            self.assertTrue(widget._check_mode)
            self.assertFalse(widget.checkbox.isHidden())

    def test_select_all_and_bulk_delete_signal(self):
        self.sidebar.toggle_check_mode(True)
        
        received_ids = []
        self.sidebar.bulk_delete_requested.connect(lambda ids: received_ids.extend(ids))

        # Check Select All
        self.sidebar.select_all_cb.setChecked(True)
        self.assertEqual(len(self.sidebar._selected_ids), 3)

        # Trigger Bulk Delete Click
        self.sidebar.delete_selected_btn.click()
        self.assertEqual(sorted(received_ids), ["c1", "c2", "c3"])
        self.assertFalse(self.sidebar._is_check_mode)


if __name__ == "__main__":
    unittest.main()
