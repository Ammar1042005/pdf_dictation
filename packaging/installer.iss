; Needs Inno Setup. Run after PyInstaller:  iscc packaging/installer.iss /DAppVersion=0.1.0
#ifndef AppVersion
#define AppVersion "0.1.0"
#endif
[Setup]
AppName=PDF Dictation
AppVersion={#AppVersion}
AppPublisher=Shaikh Mhammad Ammar
AppPublisherURL=https://github.com/Ammar1042005/pdf_dictation
AppSupportURL=https://github.com/Ammar1042005/pdf_dictation/issues
AppUpdatesURL=https://github.com/Ammar1042005/pdf_dictation/releases
DefaultDirName={autopf}\PDF Dictation
DefaultGroupName=PDF Dictation
OutputDir=..\dist
OutputBaseFilename=PDFDictation-Setup-{#AppVersion}
Compression=lzma2
SolidCompression=yes
ArchitecturesInstallIn64BitMode=x64compatible
PrivilegesRequired=admin
WizardStyle=modern
LicenseFile=..\LICENSE
[Files]
; Single-file exe - no need for recursesubdirs
Source: "..\dist\PDFDictation.exe"; DestDir: "{app}"; Flags: ignoreversion
[Icons]
Name: "{group}\PDF Dictation"; Filename: "{app}\PDFDictation.exe"
Name: "{autodesktop}\PDF Dictation"; Filename: "{app}\PDFDictation.exe"; Tasks: desktopicon
[Tasks]
Name: desktopicon; Description: "Create a desktop icon"; GroupDescription: "Additional icons:"
Name: quicklaunchicon; Description: "Create a Quick Launch icon"; GroupDescription: "Additional icons:"; Flags: unchecked
[Run]
Filename: "{app}\PDFDictation.exe"; Description: "Launch PDF Dictation"; Flags: nowait postinstall skipifsilent
