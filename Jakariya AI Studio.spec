# -*- mode: python ; coding: utf-8 -*-
"""
Jakariya AI Studio - Single File Executable PyInstaller Specification
Build target: dist/Jakariya AI Studio.exe
Creator: Md. Jakariya Sheikh
"""

import os
import sys
import PySide6
from PyInstaller.utils.hooks import collect_data_files, collect_dynamic_libs, collect_submodules

# Ensure project root is in sys.path for submodule resolution
spec_root = os.path.abspath(SPECPATH if 'SPECPATH' in globals() else os.getcwd())
if spec_root not in sys.path:
    sys.path.insert(0, spec_root)

def deduplicate_list(items):
    """Remove duplicates while preserving order."""
    seen = set()
    deduped = []
    for item in items:
        if isinstance(item, tuple):
            norm_source = os.path.normcase(os.path.abspath(item[0])) if os.path.exists(item[0]) else item[0]
            key = (norm_source, item[1])
        else:
            key = item
        if key not in seen:
            seen.add(key)
            deduped.append(item)
    return deduped

pyside6_dir = os.path.dirname(PySide6.__file__)
plugins_dir = os.path.join(pyside6_dir, "plugins")

# Core Data Files & Selective Assets
datas = []
for data_target, dest in [
    ('.env', '.'),
    ('config', 'config'),
    ('prompt', 'prompt'),
    ('README.md', '.'),
    ('LICENSE', '.'),
    ('USER_GUIDE_PROVIDERS_AND_MODELS_BANGLA.txt', '.'),
    ('Jakariya_AI_Studio_Client_Presentation.docx', '.'),
    ('cleanup_locked_temp.bat', '.'),
    ('cleanup_locked_temp.ps1', '.'),
    ('create_project_rar.bat', '.'),
]:
    if os.path.exists(data_target):
        datas.append((data_target, dest))

# Add asset subdirectories selectively (excluding backup raw files and duplicate bin)
for asset_sub in ('fonts', 'icons', 'images'):
    sub_path = os.path.join('assets', asset_sub)
    if os.path.exists(sub_path):
        datas.append((sub_path, f'assets/{asset_sub}'))

for asset_file in ('logo.ico', 'logo.png'):
    fpath = os.path.join('assets', asset_file)
    if os.path.exists(fpath):
        datas.append((fpath, 'assets'))

# Speech recognition FLAC converter (bundle once into assets/bin and speech_recognition)
bin_dir = os.path.join("assets", "bin")
flac_exe = os.path.join(bin_dir, "flac-win32.exe")
if not os.path.exists(flac_exe):
    try:
        import speech_recognition as sr
        sr_dir = os.path.dirname(os.path.abspath(sr.__file__))
        cand_flac = os.path.join(sr_dir, "flac-win32.exe")
        if os.path.exists(cand_flac):
            flac_exe = cand_flac
    except Exception:
        pass

if os.path.exists(flac_exe):
    datas.append((flac_exe, 'assets/bin'))
    datas.append((flac_exe, 'speech_recognition'))

# FFmpeg binary (bundle ONCE into assets/bin; omit redundant ffprobe to save 146MB)
ffmpeg_exe = os.path.join(bin_dir, "ffmpeg.exe")
if os.path.exists(ffmpeg_exe):
    datas.append((ffmpeg_exe, 'assets/bin'))

# Package Data Files (Only for packages that actually carry required data files)
package_data_targets = [
    'certifi',
    'qdarktheme',
    'reportlab',
    'docx',
    'edge_tts',
    'speech_recognition',
    'markdown_it',
    'pypdf',
    'pydantic',
]

for pkg in package_data_targets:
    try:
        datas.extend(collect_data_files(pkg))
    except Exception:
        pass

# Dynamic Libraries (speech_recognition, miniaudio, cffi)
binaries = []
try:
    binaries.extend(collect_dynamic_libs('speech_recognition'))
except Exception:
    pass

# Collect miniaudio and _cffi_backend C-extension modules explicitly
try:
    import _miniaudio
    pyd_path = getattr(_miniaudio, '__file__', None)
    if pyd_path and os.path.exists(pyd_path):
        binaries.append((pyd_path, '.'))
except Exception:
    pass

try:
    import _cffi_backend
    cffi_pyd = getattr(_cffi_backend, '__file__', None)
    if cffi_pyd and os.path.exists(cffi_pyd):
        binaries.append((cffi_pyd, '.'))
except Exception:
    pass

# Collect PySide6 required plugins ONCE into PySide6/plugins/<category>
# (Do NOT run collect_dynamic_libs('PySide6') which pulls in Qt6WebEngineCore (195 MB) and Qt3D/Quick)
qt_plugin_categories = (
    "platforms",
    "styles",
    "imageformats",
    "iconengines",
    "tls",
    "multimedia",
    "networkinformation",
    "platforminputcontexts",
    "generic",
)

if os.path.exists(plugins_dir):
    for plug in qt_plugin_categories:
        plug_path = os.path.join(plugins_dir, plug)
        if os.path.exists(plug_path):
            for fname in os.listdir(plug_path):
                if fname.lower().endswith((".dll", ".pyd")):
                    full_dll = os.path.join(plug_path, fname)
                    binaries.append((full_dll, f"PySide6/plugins/{plug}"))

# Collect PySide6 translations directory if present
trans_dir = os.path.join(pyside6_dir, "translations")
if os.path.exists(trans_dir):
    datas.append((trans_dir, "PySide6/translations"))


hiddenimports = [
    # UI Components & blur
    'app.ui.dwm_blur',
    'app.ui.approval_dialog',
    'app.ui.code_changes_review_dialog',
    'app.ui.document_preview_dialog',
    'app.ui.voice_settings_dialog',
    'app.ui.add_voice_dialog',
    'app.ui.rename_chat_dialog',
    'app.ui.styles',
    'app.ui.input_bar',
    'app.ui.chat_area',
    'app.ui.header',
    'app.ui.sidebar',
    'app.ui.status_bar',
    'app.ui.main_window',
    'app.ui.widgets.conversation_item',
    'app.utils.creator_photos',
    'app.utils.paths',
    'app.utils.markdown_renderer',
    'app.utils.document_detector',
    'app.utils.check_keys',
    'app.utils.color_contrast',

    # Settings & Registry
    'app.settings.provider_registry',
    'app.settings.configuration_service',
    'app.settings.settings_manager',
    'app.settings.settings_schema',
    'app.settings.defaults',
    'app.settings.key_vault',
    'app.settings.health_service',
    'app.settings.storage',
    'app.settings.validators',
    'app.settings.ui.settings_window',
    'app.settings.ui.general_page',
    'app.settings.ui.appearance_page',
    'app.settings.ui.providers_page',
    'app.settings.ui.models_page',
    'app.settings.ui.voice_page',
    'app.settings.ui.chat_page',
    'app.settings.ui.export_page',
    'app.settings.ui.advanced_page',
    'app.settings.ui.about_page',

    # Auth & Licensing
    'app.auth.auth_service',
    'app.auth.ui.auth_dialog',
    'app.licensing.license_manager',
    'app.licensing.ui.upgrade_dialog',

    # Provider implementations
    'app.providers.base.base_provider',
    'app.providers.base.provider_capabilities',
    'app.providers.base.provider_errors',
    'app.providers.base.provider_types',
    'app.providers.manager.provider_manager',
    'app.providers.manager.provider_registry',
    'app.providers.manager.health_service',
    'app.providers.models.chat_request',
    'app.providers.models.chat_response',
    'app.providers.models.model_info',
    'app.providers.implementations.google_provider',
    'app.providers.implementations.groq_provider',
    'app.providers.implementations.openrouter_provider',
    'app.providers.implementations.anthropic_provider',
    'app.providers.implementations.cerebras_provider',
    'app.providers.implementations.mistral_provider',
    'app.providers.implementations.ollama_provider',
    'app.providers.implementations.plugsky_provider',

    # Voice & Audio
    'app.voice.utils.patch_speech',
    'app.voice.utils.audio_utils',
    'app.voice.utils.device_manager',
    'app.voice.business_logic.tts.tts_provider',
    'app.voice.business_logic.tts.tts_registry',
    'app.voice.business_logic.tts.cartesia_tts',
    'app.voice.business_logic.tts.fish_audio_tts',
    'app.voice.business_logic.tts.edge_neural_tts',
    'app.voice.business_logic.tts.elevenlabs_tts',
    'app.voice.business_logic.tts.google_tts',
    'app.voice.business_logic.stt.stt_provider',
    'app.voice.business_logic.stt.stt_registry',
    'app.voice.business_logic.stt.google_stt',
    'app.voice.business_logic.stt.groq_stt',
    'app.voice.business_logic.stt.elevenlabs_stt',
    'app.voice.business_logic.audio.audio_level',
    'app.voice.business_logic.audio.audio_player',
    'app.voice.business_logic.audio.audio_stream',
    'app.voice.business_logic.audio.microphone',
    'app.voice.business_logic.audio.speaker',
    'app.voice.business_logic.pipeline.conversation_pipeline',
    'app.voice.business_logic.pipeline.interruption',
    'app.voice.business_logic.pipeline.streaming_manager',
    'app.voice.voice_controller',
    'app.voice.voice_manager',
    'app.voice.voice_service',
    'app.voice.voice_settings',
    'app.voice.voice_presets',
    'app.voice.voice_state',

    # Autonomous ReAct Agent & 12 Tools
    'app.agent.agent_engine',
    'app.agent.agent_worker',
    'app.agent.diff_tracker',
    'app.agent.tool_registry',
    'app.agent.planner.task_planner',
    'app.agent.task.task_manager',
    'app.agent.task.task_state',
    'app.agent.context.context_manager',
    'app.agent.tools.base_tool',
    'app.agent.tools.file_tool',
    'app.agent.tools.file_edit_tool',
    'app.agent.tools.file_search_tool',
    'app.agent.tools.directory_list_tool',
    'app.agent.tools.terminal_tool',
    'app.agent.tools.code_execution_tool',
    'app.agent.tools.web_search_tool',
    'app.agent.tools.document_exporter_tool',
    'app.agent.tools.code_outline_tool',
    'app.agent.tools.diagnostics_tool',
    'app.agent.tools.git_tool',
    'app.agent.tools.timeout_manager',
    'app.agent.tools.tool_cache',
    'app.agent.tools.tool_executor',

    # Document Exporting
    'app.export.export_manager',
    'app.export.export_options',
    'app.export.export_service',
    'app.export.import_service',
    'app.export.models',
    'app.export.business_logic.asset_helpers',
    'app.export.business_logic.base_exporter',
    'app.export.business_logic.code_exporter',
    'app.export.business_logic.docx_exporter',
    'app.export.business_logic.excel_exporter',
    'app.export.business_logic.exporter_registry',
    'app.export.business_logic.html_exporter',
    'app.export.business_logic.json_exporter',
    'app.export.business_logic.markdown_blocks',
    'app.export.business_logic.markdown_exporter',
    'app.export.business_logic.pdf_exporter',
    'app.export.business_logic.txt_exporter',
    'app.export.templates.docx_styles',
    'app.export.templates.html_template',
    'app.export.templates.pdf_styles',
    'app.export.utils.filename',

    # Database, Chat, Uploads & Services
    'app.chat.chat_controller',
    'app.chat.chat_manager',
    'app.chat.chat_repository',
    'app.chat.worker',
    'app.database.database',
    'app.database.database_service',
    'app.database.migrations',
    'app.uploads.file_service',
    'app.uploads.business_logic.file_parser',
    'app.uploads.business_logic.file_storage',
    'app.uploads.business_logic.file_type',
    'app.services.document_chunker',
    'app.services.rag_service',
    'app.models.attachment',
    'app.models.conversation',
    'app.models.message',
    'app.image_generation.stability_client',
    'app.image_generation.image_enhancer',
    'app.image_generation.router',
    'app.api.ClaudeClient',
    'app.api.model_catalog',
    'app.api.tavily_client',

    # Prompts & System Config
    'prompt.profile_prompt',
    'prompt.system_prompt',
    'config.config',

    # Windows C-Extensions & APIs
    '_cffi_backend',
    'cffi',
    'winreg',
    'ctypes.wintypes',
    'win32ctypes.core.ctypes',
    'win32api',
    'win32con',
    'win32gui',
    'win32process',
    'dotenv',

    # AI Provider SDKs
    'anthropic',
    'openai',
    'tavily',
    'groq',
    'google.generativeai',
    'google.ai.generativelanguage',
    'google.api_core',
    'google.auth',
    'google.protobuf',

    # Audio Packages
    'speech_recognition',
    'edge_tts',
    'edge_tts.communicate',
    'edge_tts.constants',
    'edge_tts.exceptions',
    'edge_tts.submaker',
    'aiohttp',
    'websockets',
    'yarl',
    'multidict',
    'propcache',
    'aiosignal',
    'frozenlist',
    'aiohappyeyeballs',
    'gtts',
    'miniaudio',
    '_miniaudio',
    'elevenlabs',
    'pydub',
    'audioop',
    'aifc',
    'chunk',
    'wave',
    'pyttsx3',
    'pyttsx3.drivers',
    'pyttsx3.drivers.sapi5',
    'pyttsx3.drivers.dummy',
    'comtypes',

    # Reporting & Parsing
    'reportlab',
    'reportlab.platypus',
    'reportlab.lib',
    'reportlab.lib.colors',
    'reportlab.lib.pagesizes',
    'reportlab.lib.styles',
    'reportlab.lib.units',
    'reportlab.pdfgen',
    'docx',
    'openpyxl',
    'pygments',
    'pygments.lexers',
    'pygments.styles',
    'pygments.formatters',
    'pypdf',
    'markdown',
    'markdown_it',
    'lxml',

    # HTTP & Networking
    'httpx',
    'httpcore',
    'requests',
    'urllib3',
    'anyio',
    'sniffio',
    'certifi',
    'truststore',

    # PySide6 & GUI
    'PIL',
    'qdarktheme',
    'PySide6.QtCore',
    'PySide6.QtGui',
    'PySide6.QtWidgets',
    'PySide6.QtMultimedia',
    'PySide6.QtMultimediaWidgets',
    'PySide6.QtNetwork',
    'PySide6.QtSvg',
    'PySide6.QtSvgWidgets',

    # Data Models & Utilities
    'pydantic',
    'pydantic_core',
    'sqlite3',
    'tiktoken',
    'tiktoken_ext',
    'tiktoken_ext.openai_public',
    'keyring',
    'keyring.backends',
    'keyring.backends.Windows',
    'jaraco.classes',
    'jaraco.context',
    'jaraco.functools',
    'huggingface_hub',
    'yaml',
    'regex',
    'tabulate',
    'tqdm',
    'charset_normalizer',
    'docstring_parser',
    'h11',
    'idna',
    'jiter',
    'mdurl',
    'typing_extensions',
    'typing_inspection',
    'annotated_types',
    'attrs',
    'distro',
    'et_xmlfile',
    'more_itertools',
    'packaging',
]

# Collect submodules
submodule_targets = [
    'app',
    'config',
    'prompt',
    'qdarktheme',
    'edge_tts',
]

for sm in submodule_targets:
    try:
        hiddenimports.extend(collect_submodules(sm))
    except Exception:
        pass

# Deduplicate all lists
datas = deduplicate_list(datas)
binaries = deduplicate_list(binaries)
hiddenimports = deduplicate_list(hiddenimports)

a = Analysis(
    ['main.py'],
    pathex=[spec_root],
    binaries=binaries,
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[
        'pytest', '_pytest', 'unittest', 'test', 'tests',
        'PySide6.QtWebEngine', 'PySide6.QtWebEngineCore', 'PySide6.QtWebEngineWidgets', 'PySide6.QtWebEngineQuick',
        'PySide6.Qt3DCore', 'PySide6.Qt3DRender', 'PySide6.Qt3DAnimation', 'PySide6.Qt3DExtras', 'PySide6.Qt3DInput', 'PySide6.Qt3DLogic',
        'PySide6.QtQuick', 'PySide6.QtQuick3D', 'PySide6.QtQuickControls2', 'PySide6.QtQuickWidgets',
        'PySide6.QtQml', 'PySide6.QtDesigner', 'PySide6.QtSql',
        'PySide6.QtSensors', 'PySide6.QtSerialPort', 'PySide6.QtBluetooth', 'PySide6.QtNfc',
        'PySide6.QtPositioning', 'PySide6.QtLocation', 'PySide6.QtRemoteObjects', 'PySide6.QtScxml',
        'tkinter', 'matplotlib', 'scipy',
    ],
    noarchive=False,
    optimize=0,
)
pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.zipfiles,
    a.datas,
    [],
    name='Jakariya AI Studio',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon=os.path.join('assets', 'icons', 'logo.ico'),
)
