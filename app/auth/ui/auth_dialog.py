"""PySide6 User Authentication Modal Dialog (Sign In & Sign Up with 3-Day Trial)."""

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
    QTabWidget,
    QWidget,
    QFrame,
    QMessageBox,
)

from app.auth.auth_service import AuthService
from app.utils.paths import get_resource_path


class AuthDialog(QDialog):
    """User Authentication dialog supporting Email Sign In and Sign Up with a 3-Day Trial."""

    authenticated = Signal(str)  # Emits user email on success

    def __init__(self, parent: QWidget = None, theme: str = "light"):
        super().__init__(parent)
        self.theme = str(theme).lower()
        self.is_dark = self.theme in ("dark", "oled", "neon")
        self.auth_service = AuthService.instance()

        self.setWindowTitle("Jakariya AI Studio — Account Login & 3-Day Trial")
        self.setFixedSize(480, 520)
        self.setModal(True)

        icon_path = get_resource_path("assets", "logo.ico")
        if icon_path.exists():
            self.setWindowIcon(QIcon(str(icon_path)))

        self._init_ui()

    def _init_ui(self) -> None:
        bg_color = "#12121E" if self.is_dark else "#F8FAFC"
        text_color = "#F8FAFC" if self.is_dark else "#0F172A"
        input_bg = "#1E1E2E" if self.is_dark else "#FFFFFF"
        border_color = "#334155" if self.is_dark else "#CBD5E1"
        tab_bg = "#1E1E2E" if self.is_dark else "#FFFFFF"

        self.setStyleSheet(f"""
            QDialog {{
                background-color: {bg_color};
                color: {text_color};
            }}
            QLabel {{
                color: {text_color};
            }}
            QLineEdit {{
                background-color: {input_bg};
                color: {text_color};
                border: 1px solid {border_color};
                border-radius: 8px;
                padding: 10px 12px;
                font-size: 13px;
            }}
            QLineEdit:focus {{
                border: 2px solid #6366F1;
            }}
            QTabWidget::pane {{
                border: 1px solid {border_color};
                border-radius: 12px;
                background-color: {tab_bg};
                padding: 12px;
            }}
            QTabBar::tab {{
                background-color: {'#181825' if self.is_dark else '#E2E8F0'};
                color: {'#94A3B8' if self.is_dark else '#64748B'};
                padding: 8px 24px;
                margin-right: 4px;
                border-top-left-radius: 8px;
                border-top-right-radius: 8px;
                font-weight: 600;
                font-size: 13px;
            }}
            QTabBar::tab:selected {{
                background-color: #6366F1;
                color: #FFFFFF;
            }}
        """)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 20, 24, 20)
        layout.setSpacing(14)

        # Header Title
        title_box = QVBoxLayout()
        header_title = QLabel("🚀 Jakariya AI Studio")
        header_title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        header_title.setStyleSheet("font-size: 18px; font-weight: 800; color: #4F46E5;")

        subtitle = QLabel("লগইন করুন অথবা ৩ দিনের ফ্রি প্রিমিয়াম ট্রায়াল শুরু করুন")
        subtitle.setAlignment(Qt.AlignmentFlag.AlignCenter)
        subtitle.setStyleSheet(f"font-size: 12px; color: {'#94A3B8' if self.is_dark else '#64748B'};")

        title_box.addWidget(header_title)
        title_box.addWidget(subtitle)
        layout.addLayout(title_box)

        # Tabs for Sign In & Sign Up
        self.tabs = QTabWidget()
        self.tab_login = QWidget()
        self.tab_signup = QWidget()

        self._setup_login_tab()
        self._setup_signup_tab()

        self.tabs.addTab(self.tab_login, "🔑 লগইন (Sign In)")
        self.tabs.addTab(self.tab_signup, "✨ সাইন-আপ (3-Day Trial)")
        layout.addWidget(self.tabs, 1)

        # Message status label
        self.status_label = QLabel("")
        self.status_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.status_label.setWordWrap(True)
        self.status_label.setStyleSheet("font-size: 12px; font-weight: 600;")
        layout.addWidget(self.status_label)

    def _setup_login_tab(self) -> None:
        l = QVBoxLayout(self.tab_login)
        l.setContentsMargins(12, 16, 12, 16)
        l.setSpacing(10)

        l.addWidget(QLabel("ইমেইল অ্যাড্রেস:"))
        self.login_email = QLineEdit()
        self.login_email.setPlaceholderText("yourname@example.com")
        l.addWidget(self.login_email)

        l.addWidget(QLabel("পাসওয়ার্ড:"))
        self.login_pwd = QLineEdit()
        self.login_pwd.setEchoMode(QLineEdit.EchoMode.Password)
        self.login_pwd.setPlaceholderText("••••••••")
        l.addWidget(self.login_pwd)

        l.addSpacing(6)
        btn_login = QPushButton("লগইন করুন (Sign In)")
        btn_login.setFixedHeight(40)
        btn_login.setCursor(Qt.CursorShape.PointingHandCursor)
        btn_login.setStyleSheet("""
            QPushButton {
                background-color: #4F46E5;
                color: #FFFFFF;
                font-weight: 700;
                font-size: 14px;
                border-radius: 8px;
            }
            QPushButton:hover { background-color: #4338CA; }
        """)
        btn_login.clicked.connect(self._handle_login)
        l.addWidget(btn_login)
        l.addStretch()

    def _setup_signup_tab(self) -> None:
        l = QVBoxLayout(self.tab_signup)
        l.setContentsMargins(12, 12, 12, 12)
        l.setSpacing(8)

        # 3-Day Trial Announcement Banner
        banner = QFrame()
        banner_bg = "#312E81" if self.is_dark else "#EEF2FF"
        banner_border = "#4338CA" if self.is_dark else "#C7D2FE"
        banner_fg = "#C7D2FE" if self.is_dark else "#3730A3"
        banner.setStyleSheet(f"""
            QFrame {{
                background-color: {banner_bg};
                border: 1px solid {banner_border};
                border-radius: 8px;
                padding: 6px 10px;
            }}
        """)
        banner_layout = QHBoxLayout(banner)
        banner_layout.setContentsMargins(6, 6, 6, 6)
        banner_text = QLabel("🎁 <b>৩ দিনের ফ্রি ট্রায়াল:</b> সাইন-আপ করলেই Cartesia লাইভ ভয়েস, FLUX.1 ও আনলিমিটেড AI এজেন্ট বিনামূল্যে আনলক হবে!")
        banner_text.setWordWrap(True)
        banner_text.setStyleSheet(f"color: {banner_fg}; font-size: 11.5px;")
        banner_layout.addWidget(banner_text)
        l.addWidget(banner)

        l.addWidget(QLabel("আপনার নাম:"))
        self.signup_name = QLineEdit()
        self.signup_name.setPlaceholderText("Md. Jakariya")
        l.addWidget(self.signup_name)

        l.addWidget(QLabel("ইমেইল অ্যাড্রেস:"))
        self.signup_email = QLineEdit()
        self.signup_email.setPlaceholderText("yourname@example.com")
        l.addWidget(self.signup_email)

        l.addWidget(QLabel("পাসওয়ার্ড (কমপক্ষে ৬ অক্ষর):"))
        self.signup_pwd = QLineEdit()
        self.signup_pwd.setEchoMode(QLineEdit.EchoMode.Password)
        self.signup_pwd.setPlaceholderText("••••••••")
        l.addWidget(self.signup_pwd)

        l.addSpacing(4)
        btn_signup = QPushButton("⚡ সাইন-আপ করুন (Start 3-Day Pro Trial)")
        btn_signup.setFixedHeight(40)
        btn_signup.setCursor(Qt.CursorShape.PointingHandCursor)
        btn_signup.setStyleSheet("""
            QPushButton {
                background-color: #10B981;
                color: #FFFFFF;
                font-weight: 700;
                font-size: 13.5px;
                border-radius: 8px;
            }
            QPushButton:hover { background-color: #059669; }
        """)
        btn_signup.clicked.connect(self._handle_signup)
        l.addWidget(btn_signup)
        l.addStretch()

    def _handle_login(self) -> None:
        email = self.login_email.text().strip()
        pwd = self.login_pwd.text().strip()
        ok, msg = self.auth_service.login(email, pwd)
        if ok:
            self.status_label.setStyleSheet("color: #10B981;")
            self.status_label.setText(msg)
            self.authenticated.emit(email)
            self.accept()
        else:
            self.status_label.setStyleSheet("color: #EF4444;")
            self.status_label.setText(msg)

    def _handle_signup(self) -> None:
        name = self.signup_name.text().strip()
        email = self.signup_email.text().strip()
        pwd = self.signup_pwd.text().strip()
        ok, msg = self.auth_service.signup(email, pwd, name=name)
        if ok:
            self.status_label.setStyleSheet("color: #10B981;")
            self.status_label.setText(msg)
            self.authenticated.emit(email)
            QMessageBox.information(
                self,
                "🎉 ৩ দিনের ফ্রি ট্রায়াল সক্রিয়!",
                "অভিনন্দন! আপনার ৩ দিনের সম্পূর্ণ ফ্রি প্রিমিয়াম ট্রায়াল শুরু হয়েছে। সমস্ত প্রিমিয়াম ফিচার এখন সক্রিয়।"
            )
            self.accept()
        else:
            self.status_label.setStyleSheet("color: #EF4444;")
            self.status_label.setText(msg)
