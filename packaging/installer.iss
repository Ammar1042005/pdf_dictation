; Needs Inno Setup. Run after PyInstaller:  iscc packaging\installer.iss /DAppVersion=0.1.0
#ifndef AppVersion
#define AppVersion "0.1.0"
#endif
[Setup]
AppName=PDF Dictation
AppVersion={#AppVersion}
DefaultDirName={autopf}\PDF Dictation
DefaultGroupName=PDF Dictation
OutputDir=..\dist
OutputBaseFilename=PDFDictation-Setup-{#AppVersion}
Compression=lzma2
ArchitecturesInstallIn64BitMode=x64compatible
[Files]
Source: "..\dist\PDFDictation\*"; DestDir: "{app}"; Flags: recursesubdirs
[Icons]
Name: "{group}\PDF Dictation"; Filename: "{app}\PDFDictation.exe"
Name: "{autodesktop}\PDF Dictation"; Filename: "{app}\PDFDictation.exe"; Tasks: desktopicon
[Tasks]
Name: desktopicon; Description: "Create a desktop icon"
