# -*- mode: python ; coding: utf-8 -*-
"""
Jakariya AI Studio - Folder / Directory Layout PyInstaller Specification
Build target: dist/Jakariya AI Studio/
Used by Inno Setup (Jakariya_AI_Studio_Setup.iss)
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
    ('.env', '.env'),
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
    "audio",
    "translations",
)

if os.path.exists(plugins_dir):
    for plug in qt_plugin_categories:
        plug_path = os.path.join(plugins_dir, plug)
        if os.path.exists(plug_path):
            for fname in os.listdir(plug_path):
                if fname.lower().endswith((".dll", ".pyd")):
                    full_dll = os.path.join(plug_path, fname)
                    binaries.append((full_dll, f"PySide6/plugins/{plug}"))


hiddenimports = [
    # UI Components & blur
    'app.ui.dwm_blur',
    'app.ui.approval_dialog',
    'app.ui.document_preview_dialog',
    'app.ui.voice_settings_dialog',
    'app.ui.styles',
    'app.ui.input_bar',
    'app.ui.chat_area',
    'app.ui.main_window',
    'app.utils.creator_photos',
    'app.utils.paths',
    'app.utils.markdown_renderer',
    'app.utils.document_detector',
    'app.utils.check_keys',

    # Settings & Registry
    'app.settings.provider_registry',
    'app.settings.configuration_service',
    'app.settings.settings_manager',
    'app.settings.settings_schema',
    'app.settings.defaults',
    'app.settings.keyring_service',
    'app.settings.ui.settings_window',
    'app.settings.ui.providers_page',

    # Provider implementations
    'app.providers.base.base_provider',
    'app.providers.base.provider_capabilities',
    'app.providers.base.provider_errors',
    'app.providers.manager.provider_manager',
    'app.providers.implementations.google_provider',
    'app.providers.implementations.groq_provider',
    'app.providers.implementations.openrouter_provider',
    'app.providers.implementations.anthropic_provider',
    'app.providers.implementations.cerebras_provider',
    'app.providers.implementations.ollama_provider',
    'app.providers.implementations.plugsky_provider',

    # Voice & Audio
    'app.voice.utils.patch_speech',
    'app.voice.utils.audio_utils',
    'app.voice.business_logic.tts.tts_provider',
    'app.voice.business_logic.tts.tts_registry',
    'app.voice.business_logic.tts.cartesia_tts',
    'app.voice.business_logic.tts.fish_audio_tts',
    'app.voice.business_logic.tts.edge_neural_tts',
    'app.voice.business_logic.tts.google_tts',
    'app.voice.business_logic.stt.stt_provider',
    'app.voice.business_logic.stt.stt_registry',
    'app.voice.business_logic.stt.google_stt',
    'app.voice.voice_controller',
    'app.voice.voice_manager',
    'app.voice.voice_service',
    'app.voice.voice_settings',

    # Autonomous ReAct Agent & 12 Tools
    'app.agent.agent_engine',
    'app.agent.agent_worker',
    'app.agent.tool_registry',
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
    'app.agent.tools.tool_executor',

    # Document Exporting
    'app.export.exporter_factory',
    'app.export.pdf_exporter',
    'app.export.docx_exporter',
    'app.export.xlsx_exporter',
    'app.export.html_exporter',
    'app.export.markdown_exporter',
    'app.export.text_exporter',

    # Database & Image Generation
    'app.database.database_service',
    'app.image_generation.stability_client',
    'app.image_generation.flux_client',
    'app.image_generation.image_enhancer',

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
    [],
    exclude_binaries=True,
    name='Jakariya AI Studio',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon=os.path.join('assets', 'icons', 'logo.ico'),
)

coll = COLLECT(
    exe,
    a.binaries,
    a.zipfiles,
    a.datas,
    strip=False,
    upx=False,
    upx_exclude=[],
    name='Jakariya AI Studio',
)
