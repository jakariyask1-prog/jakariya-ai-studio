; ============================================================================
; Jakariya AI Studio - Inno Setup Script
; Production-Ready Windows Installer Configuration
; Creator: Md. Jakariya Sheikh
; ============================================================================

#define MyAppName "Jakariya AI Studio"
#define MyAppVersion "2.0.0"
#define MyAppPublisher "Md. Jakariya Sheikh"
#define MyAppURL "https://github.com/"
#define MyAppExeName "Jakariya AI Studio.exe"

[Setup]
; Unique Application ID (Double opening brace {{ escapes literal '{' in Inno Setup)
AppId={{A4F92E31-7B8C-4D5E-91A2-8C3F5E7B9012}
AppName={#MyAppName}
AppVersion={#MyAppVersion}
AppVerName={#MyAppName} v{#MyAppVersion}
AppPublisher={#MyAppPublisher}
AppPublisherURL={#MyAppURL}
AppSupportURL={#MyAppURL}
AppUpdatesURL={#MyAppURL}

; Installation Target Directories & Privileges
DefaultDirName={autopf}\{#MyAppName}
DefaultGroupName={#MyAppName}
AllowNoIcons=yes
LicenseFile=LICENSE
OutputDir=dist
OutputBaseFilename=Jakariya_AI_Studio_Setup_v{#MyAppVersion}
SetupIconFile=assets\icons\logo.ico
UninstallDisplayIcon={app}\{#MyAppExeName},0

; High-Performance Fast Compression
Compression=lzma2/fast
SolidCompression=yes
WizardStyle=modern
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible
PrivilegesRequired=admin
UsedUserAreasWarning=no

; Process Management & Upgrade Behavior
CloseApplications=force
CloseApplicationsFilter={#MyAppExeName}
RestartApplications=no

[Languages]
Name: "english"; MessagesFile: "compiler:Default.isl"

[Tasks]
Name: "desktopicon"; Description: "{cm:CreateDesktopIcon}"; GroupDescription: "{cm:AdditionalIcons}"; Flags: unchecked

[Files]
; Main Executable & Bundled Dependencies (Directory mode from main.spec)
Source: "dist\Jakariya AI Studio\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs skipifsourcedoesntexist

; Standalone Executable (Single-file mode from Jakariya AI Studio.spec)
Source: "dist\{#MyAppExeName}"; DestDir: "{app}"; Flags: ignoreversion skipifsourcedoesntexist

; Environment Configuration Template (Preserved if present on upgrade)
Source: ".env"; DestDir: "{app}"; Flags: onlyifdoesntexist uninsneveruninstall skipifsourcedoesntexist

; Documentation, User Guides & Sample Outlines
Source: "README.md"; DestDir: "{app}\docs"; Flags: ignoreversion skipifsourcedoesntexist
Source: "USER_GUIDE_PROVIDERS_AND_MODELS_BANGLA.txt"; DestDir: "{app}\docs"; Flags: ignoreversion skipifsourcedoesntexist
Source: "LICENSE"; DestDir: "{app}\docs"; Flags: ignoreversion skipifsourcedoesntexist
Source: "software_engineer_resume_outline.md"; DestDir: "{app}\docs"; Flags: ignoreversion skipifsourcedoesntexist
Source: "red_parrot_description.txt"; DestDir: "{app}\docs"; Flags: ignoreversion skipifsourcedoesntexist

[Dirs]
; Writable User Data Directories created in LocalAppData
Name: "{localappdata}\Jakariya AI Studio"
Name: "{localappdata}\Jakariya AI Studio\generated_images"
Name: "{localappdata}\Jakariya AI Studio\uploads"
Name: "{localappdata}\Jakariya AI Studio\logs"
Name: "{localappdata}\Jakariya AI Studio\exports"
Name: "{localappdata}\Jakariya AI Studio\chats"

[Icons]
Name: "{autoprograms}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"; WorkingDir: "{app}"
Name: "{autodesktop}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"; WorkingDir: "{app}"; Tasks: desktopicon

[Registry]
; App Path Registry Entries for Win+R / Windows Search Execution
Root: HKLM; Subkey: "SOFTWARE\Microsoft\Windows\CurrentVersion\App Paths\{#MyAppExeName}"; ValueType: string; ValueName: ""; ValueData: "{app}\{#MyAppExeName}"; Flags: uninsdeletekey
Root: HKLM; Subkey: "SOFTWARE\Microsoft\Windows\CurrentVersion\App Paths\{#MyAppExeName}"; ValueType: string; ValueName: "Path"; ValueData: "{app}"; Flags: uninsdeletekey

[Run]
Filename: "{app}\{#MyAppExeName}"; Description: "{cm:LaunchProgram,Jakariya AI Studio}"; Flags: nowait postinstall skipifsilent

[Code]
// ============================================================================
// Uninstall Custom Behavior: Optional Purge of Personal User Data in LocalAppData
// ============================================================================
procedure CurUninstallStepChanged(JustAfter: TUninstallStep);
var
  DataDir: String;
begin
  if JustAfter = usUninstall then
  begin
    DataDir := ExpandConstant('{localappdata}\Jakariya AI Studio');
    if DirExists(DataDir) then
    begin
      if MsgBox('Do you want to delete your personal user data (chat history, settings, database, uploaded files, and generated images)?' + #13#10 + #13#10 +
                'Click YES to completely purge user data.' + #13#10 +
                'Click NO to keep your data intact for future reinstallations.',
                mbConfirmation, MB_YESNO or MB_DEFBUTTON2) = IDYES then
      begin
        DelTree(DataDir, True, True, True);
      end;
    end;
  end;
end;
