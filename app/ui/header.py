from PySide6.QtWidgets import (
    QWidget,
    QLabel,
    QComboBox,
    QHBoxLayout,
    QMenu,
    QToolButton,
)
from PySide6.QtCore import Signal, Qt

from app.api.model_catalog import get_provider_options, get_model_options


class Header(QWidget):
    export_requested = Signal(str)
    settings_requested = Signal()
    upgrade_requested = Signal()
    auth_requested = Signal()

    def __init__(self):
        super().__init__()

        self.setFixedHeight(54)
        self.setStyleSheet("""
            Header {
                background-color: #FFFFFF;
                border-bottom: 1px solid #E2E8F0;
            }
        """)

        layout = QHBoxLayout(self)
        layout.setContentsMargins(18, 8, 18, 8)
        layout.setSpacing(8)

        self._raw_title = "New Chat"
        self.chat_title = QLabel("New Chat")
        self.chat_title.setAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)
        from PySide6.QtWidgets import QSizePolicy
        self.chat_title.setSizePolicy(QSizePolicy.Policy.Ignored, QSizePolicy.Policy.Preferred)
        self.chat_title.setMinimumWidth(0)

        # Plan Status & Upgrade Badge Button
        self.plan_badge_btn = QToolButton()
        self.plan_badge_btn.setFixedHeight(34)
        self.plan_badge_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.plan_badge_btn.clicked.connect(self.upgrade_requested.emit)

        # Provider Selector (Pill Dropdown)
        self.provider_selector = QComboBox()
        self.provider_selector.setFixedHeight(34)
        self.provider_selector.setToolTip("Select AI Provider")

        # Model Selector (Pill Dropdown)
        self.model_selector = QComboBox()
        self.model_selector.setFixedHeight(34)
        self.model_selector.setToolTip("Select AI Model")

        # Sleek Export ToolButton (Icon-only matching settings button)
        self.export_button = QToolButton()
        self.export_button.setText("📥")
        self.export_button.setFixedSize(34, 34)
        self.export_button.setPopupMode(QToolButton.ToolButtonPopupMode.InstantPopup)
        self.export_button.setToolTip("Export this conversation (PDF, Word, Excel, Markdown, Text)")
        self.export_menu = QMenu(self.export_button)
        self.export_button.setMenu(self.export_menu)

        # Sleek Settings Icon ToolButton
        self.settings_button = QToolButton()
        self.settings_button.setText("⚙️")
        self.settings_button.setFixedSize(34, 34)
        self.settings_button.setToolTip("Open Application Settings & Personalization")
        self.settings_button.clicked.connect(self.settings_requested.emit)

        # Assemble Header Layout
        layout.addWidget(self.chat_title, 1)
        layout.addWidget(self.plan_badge_btn, 0)
        layout.addWidget(self.provider_selector, 0)
        layout.addWidget(self.model_selector, 0)
        layout.addWidget(self.export_button, 0)
        layout.addWidget(self.settings_button, 0)

        # Dynamic Provider & Model loading
        self.provider_selector.currentIndexChanged.connect(self._on_provider_changed)
        self.refresh_providers_and_models()

        self._theme = "light"
        self.apply_theme("light")

    def apply_theme(self, theme_name: str) -> None:
        """Update header background and dropdown QSS styles according to theme."""
        self._theme = theme_name
        from app.ui.styles import get_theme_palette, get_pill_combobox_style, apply_combobox_theme
        p = get_theme_palette(theme_name)

        self.setStyleSheet(f"""
            Header {{
                background-color: {p['bg_header']};
                border-bottom: 1px solid {p['border_header']};
            }}
        """)
        self.chat_title.setStyleSheet(f"font-size: 15px; font-weight: 700; color: {p['text_header_title']};")

        combo_qss = get_pill_combobox_style(theme_name)
        self.provider_selector.setStyleSheet(combo_qss)
        self.model_selector.setStyleSheet(combo_qss)
        apply_combobox_theme(self.provider_selector, theme_name)
        apply_combobox_theme(self.model_selector, theme_name)

        tool_btn_style = f"""
            QToolButton {{
                background-color: {p['btn_secondary_bg']};
                color: {p['btn_secondary_text']};
                border: 1px solid {p['btn_secondary_border']};
                border-radius: 10px;
                padding: 0px;
                font-size: 12pt;
            }}
            QToolButton:hover {{
                background-color: {p['btn_secondary_hover']};
                border-color: {p['border_capsule_focus']};
            }}
            QToolButton::menu-indicator {{
                image: none;
            }}
        """
        self.export_button.setStyleSheet(tool_btn_style)

        icon_btn_style = f"""
            QToolButton {{
                background-color: {p['btn_secondary_bg']};
                color: {p['btn_secondary_text']};
                border: 1px solid {p['btn_secondary_border']};
                border-radius: 10px;
                font-size: 12pt;
            }}
            QToolButton:hover {{
                background-color: {p['btn_secondary_hover']};
                border-color: {p['border_capsule_focus']};
            }}
        """
        self.settings_button.setStyleSheet(icon_btn_style)
        self.refresh_plan_badge()
        self._update_elided_title()

    def refresh_plan_badge(self) -> None:
        """Update badge text and visual appearance based on 3-day trial or Pro status."""
        try:
            from app.licensing.license_manager import LicenseManager
            status = LicenseManager.instance().get_plan_status()
            tier = status.get("tier", "free")
            badge = status.get("badge", "Free Plan")

            if tier == "premium":
                self.plan_badge_btn.setText("👑 Pro")
                self.plan_badge_btn.setToolTip("👑 Pro Membership Active — ক্লিক করে লাইসেন্স ও সুবিধা দেখুন")
                self.plan_badge_btn.setStyleSheet("""
                    QToolButton {
                        background-color: #FEF3C7;
                        color: #92400E;
                        border: 1px solid #F59E0B;
                        border-radius: 8px;
                        padding: 3px 10px;
                        font-weight: 700;
                        font-size: 9pt;
                    }
                    QToolButton:hover {
                        background-color: #FDE68A;
                    }
                """)
            elif tier == "trial":
                self.plan_badge_btn.setText("⚡ Trial")
                self.plan_badge_btn.setToolTip(f"⚡ {status.get('label', '')} — ৩ দিনের জন্য সকল সুবিধা সক্রিয়! আপগ্রেড করতে ক্লিক করুন")
                self.plan_badge_btn.setStyleSheet("""
                    QToolButton {
                        background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #4F46E5, stop:1 #7C3AED);
                        color: #FFFFFF;
                        border: 1px solid #6366F1;
                        border-radius: 8px;
                        padding: 3px 10px;
                        font-weight: 700;
                        font-size: 9pt;
                    }
                    QToolButton:hover {
                        background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #4338CA, stop:1 #6D28D9);
                    }
                """)
            else:
                self.plan_badge_btn.setText("⚡ Pro")
                self.plan_badge_btn.setToolTip("ফ্রি প্ল্যান সক্রিয় — ৩ দিনের ট্রায়াল শেষ হয়েছে। Pro-তে আপগ্রেড করতে ক্লিক করুন")
                from app.ui.styles import get_theme_palette
                p = get_theme_palette(getattr(self, "_theme", "light"))
                self.plan_badge_btn.setStyleSheet(f"""
                    QToolButton {{
                        background-color: {p['btn_secondary_bg']};
                        color: {p['btn_secondary_text']};
                        border: 1px solid {p['btn_secondary_border']};
                        border-radius: 8px;
                        padding: 3px 10px;
                        font-weight: 600;
                        font-size: 9pt;
                    }}
                    QToolButton:hover {{
                        background-color: {p['btn_secondary_hover']};
                        color: {p['input_text']};
                        border-color: {p['border_capsule_focus']};
                    }}
                """)
        except Exception:
            self.plan_badge_btn.setText("⚡ Plan")

    def resizeEvent(self, event) -> None:
        super().resizeEvent(event)
        self._update_elided_title()

    def _update_elided_title(self) -> None:
        """Elide title text cleanly if header space is constrained."""
        avail_width = self.chat_title.width()
        if avail_width <= 10:
            avail_width = 250
        from PySide6.QtGui import QFontMetrics
        metrics = QFontMetrics(self.chat_title.font())
        elided = metrics.elidedText(self._raw_title, Qt.TextElideMode.ElideRight, avail_width)
        self.chat_title.setText(elided)

    def refresh_providers_and_models(self) -> None:
        """Populate provider selector and trigger model list refresh."""
        self.provider_selector.blockSignals(True)
        self.provider_selector.clear()
        providers = get_provider_options()
        for display_name, p_id in providers:
            self.provider_selector.addItem(display_name, p_id)
        self.provider_selector.blockSignals(False)
        self._on_provider_changed()

    def _on_provider_changed(self) -> None:
        """Refresh model dropdown whenever the active provider is changed."""
        p_id = str(self.provider_selector.currentData() or "")
        self.model_selector.blockSignals(True)
        self.model_selector.clear()
        models = get_model_options(p_id if p_id else None)
        for display_name, model_id in models:
            self.model_selector.addItem(display_name, model_id)

        # Pre-select configured default model from settings if present
        try:
            from app.settings.settings_manager import SettingsManager
            cfg_model = SettingsManager.instance().service.schema.models.chat_model
            if cfg_model:
                idx = self.model_selector.findData(cfg_model)
                if idx >= 0:
                    self.model_selector.setCurrentIndex(idx)
        except Exception:
            pass
        self.model_selector.blockSignals(False)

    def set_chat_title(self, title: str) -> None:
        """Show the active conversation title in the application header."""
        self._raw_title = title
        self.chat_title.setToolTip(title)
        self._update_elided_title()

    def selected_model(self) -> str:
        """Return the API identifier for the model currently shown to the user."""
        return str(self.model_selector.currentData() or "")

    def selected_provider(self) -> str:
        """Return the identifier for the provider currently selected by the user."""
        return str(self.provider_selector.currentData() or "")

    def set_export_formats(self, formats) -> None:
        """Populate the menu from exporter-provided metadata."""
        self.export_menu.clear()
        for export_format in formats:
            action = self.export_menu.addAction(export_format.display_name)
            action.setData(export_format.format_id)
            action.triggered.connect(
                lambda _checked=False, format_id=export_format.format_id: self.export_requested.emit(format_id)
            )
        self.export_button.setEnabled(bool(formats))

