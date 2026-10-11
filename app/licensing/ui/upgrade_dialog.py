"""PySide6 Upgrade to Pro & License Key Activation Modal Dialog."""

from __future__ import annotations

from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QIcon
from PySide6.QtWidgets import (
    QDialog,
    QVBoxLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QFrame,
    QWidget,
    QMessageBox,
)

from app.licensing.license_manager import LicenseManager
from app.utils.paths import get_resource_path


class UpgradeDialog(QDialog):
    """Dialog displaying Pro benefits and allowing users to activate a License Key."""

    license_activated = Signal()

    def __init__(self, parent: QWidget = None, theme: str = "light"):
        super().__init__(parent)
        self.theme = str(theme).lower()
        self.is_dark = self.theme in ("dark", "oled", "neon")
        self.license_manager = LicenseManager.instance()

        self.setWindowTitle("Jakariya AI Studio — 👑 Upgrade to Pro")
        self.setFixedSize(520, 560)
        self.setModal(True)

        icon_path = get_resource_path("assets", "logo.ico")
        if icon_path.exists():
            self.setWindowIcon(QIcon(str(icon_path)))

        self._init_ui()

    def _init_ui(self) -> None:
        bg_color = "#12121E" if self.is_dark else "#F8FAFC"
        text_color = "#F8FAFC" if self.is_dark else "#0F172A"
        card_bg = "#1E1E2E" if self.is_dark else "#FFFFFF"
        border_color = "#334155" if self.is_dark else "#CBD5E1"

        self.setStyleSheet(f"""
            QDialog {{
                background-color: {bg_color};
                color: {text_color};
            }}
            QLabel {{
                color: {text_color};
            }}
            QLineEdit {{
                background-color: {card_bg};
                color: {text_color};
                border: 1px solid {border_color};
                border-radius: 8px;
                padding: 10px 12px;
                font-size: 13px;
                font-family: 'Consolas', monospace;
            }}
            QLineEdit:focus {{
                border: 2px solid #F59E0B;
            }}
        """)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 20, 24, 20)
        layout.setSpacing(14)

        # Header Title
        title_box = QVBoxLayout()
        header_title = QLabel("👑 Jakariya AI Studio Pro")
        header_title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        header_title.setStyleSheet("font-size: 20px; font-weight: 800; color: #F59E0B;")

        status = self.license_manager.get_plan_status()
        badge_text = status.get("badge", "Free Plan")
        subtitle = QLabel(f"বর্তমান স্ট্যাটাস: <b>{badge_text}</b> — আনলক করুন সমস্ত অ্যাডভান্সড এআই ইঞ্জিন")
        subtitle.setAlignment(Qt.AlignmentFlag.AlignCenter)
        subtitle.setStyleSheet(f"font-size: 12.5px; color: {'#94A3B8' if self.is_dark else '#64748B'};")

        title_box.addWidget(header_title)
        title_box.addWidget(subtitle)
        layout.addLayout(title_box)

        # Features Card Frame
        features_card = QFrame()
        features_card.setStyleSheet(f"""
            QFrame {{
                background-color: {card_bg};
                border: 1px solid {border_color};
                border-radius: 12px;
                padding: 14px;
            }}
        """)
        f_layout = QVBoxLayout(features_card)
        f_layout.setSpacing(8)

        pro_perks = [
            ("⚡", "<b>Cartesia AI Sonic Voice</b> — ১ সেকেন্ডের কম সময়ে অতিপ্রাকৃতিক লাইভ ভয়েস রেসপন্স"),
            ("🎨", "<b>FLUX.1-schnell Ultra-HD Studio</b> — ফটো-রিয়েলিস্টিক হাই রেজোলিউশন ইমেজ জেনারেশন"),
            ("🤖", "<b>আনলিমিটেড ReAct Agent</b> — ১২টি স্যান্ডবক্সড টুল ও ১-ক্লিক Auto-Run মোড"),
            ("🎙️", "<b>Fish Audio & ElevenLabs</b> — প্রফেশনাল নিউরাল এবং পার্সোনাল ভয়েস ক্লোনিং"),
            ("📄", "<b>স্মার্ট ৮-ফরম্যাট এক্সপোর্টার</b> — বাংলা ইউনিকোড ফন্টসহ স্টাইলিশ PDF, Word DOCX ও Excel"),
        ]

        for icon, text in pro_perks:
            row = QHBoxLayout()
            icon_lbl = QLabel(icon)
            icon_lbl.setStyleSheet("font-size: 15px;")
            desc_lbl = QLabel(text)
            desc_lbl.setWordWrap(True)
            desc_lbl.setStyleSheet(f"font-size: 12px; color: {text_color}; line-height: 1.4;")
            row.addWidget(icon_lbl)
            row.addWidget(desc_lbl, 1)
            f_layout.addLayout(row)

        layout.addWidget(features_card)

        # License Activation Section
        act_box = QVBoxLayout()
        act_box.setSpacing(8)
        act_lbl = QLabel("🔑 <b>লাইসেন্স কি (License Key) সক্রিয় করুন:</b>")
        act_lbl.setStyleSheet("font-size: 13px;")
        act_box.addWidget(act_lbl)

        input_row = QHBoxLayout()
        self.key_input = QLineEdit()
        self.key_input.setPlaceholderText("JAK-PRO-XXXX-XXXX-XXXX")
        self.key_input.setFixedHeight(40)

        btn_activate = QPushButton("সক্রিয় করুন (Activate)")
        btn_activate.setFixedHeight(40)
        btn_activate.setCursor(Qt.CursorShape.PointingHandCursor)
        btn_activate.setStyleSheet("""
            QPushButton {
                background-color: #F59E0B;
                color: #FFFFFF;
                font-weight: 700;
                font-size: 13px;
                border-radius: 8px;
                padding: 0 16px;
            }
            QPushButton:hover { background-color: #D97706; }
        """)
        btn_activate.clicked.connect(self._handle_activation)

        input_row.addWidget(self.key_input, 1)
        input_row.addWidget(btn_activate)
        act_box.addLayout(input_row)

        layout.addLayout(act_box)

        # Payment / Purchase contact info
        info_frame = QFrame()
        info_frame.setStyleSheet("""
            QFrame {
                background-color: #FEF3C7;
                border: 1px solid #FDE68A;
                border-radius: 8px;
                padding: 8px;
            }
        """)
        info_layout = QVBoxLayout(info_frame)
        contact_txt = QLabel(
            "💳 <b>প্রো লাইসেন্স কেনার জন্য:</b><br/>"
            "বিকাশ/নগদ পেমেন্ট অথবা আন্তর্জাতিক ক্রয়ের জন্য যোগাযোগ করুন: <b>jakariyask1@gmail.com</b>"
        )
        contact_txt.setAlignment(Qt.AlignmentFlag.AlignCenter)
        contact_txt.setStyleSheet("color: #92400E; font-size: 11.5px;")
        info_layout.addWidget(contact_txt)
        layout.addWidget(info_frame)

        # Close button
        btn_close = QPushButton("বন্ধ করুন (Close)")
        btn_close.setFixedHeight(34)
        btn_close.setCursor(Qt.CursorShape.PointingHandCursor)
        btn_close.clicked.connect(self.reject)
        layout.addWidget(btn_close)

    def _handle_activation(self) -> None:
        key = self.key_input.text().strip()
        ok, msg = self.license_manager.activate_license_key(key)
        if ok:
            QMessageBox.information(self, "সফল!", msg)
            self.license_activated.emit()
            self.accept()
        else:
            QMessageBox.warning(self, "ভুল লাইসেন্স কি", msg)
