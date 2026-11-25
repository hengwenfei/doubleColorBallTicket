#ifndef SourceDir
  #define SourceDir "."
#endif

[Setup]
AppId={{B48905A2-F7E5-4A7B-A2C4-A377BA6BF589}
AppName=双色球选号工具
AppVersion=1.0.0
DefaultDirName={localappdata}\Programs\双色球选号工具
DefaultGroupName=双色球选号工具
OutputDir={#SourceDir}\dist
OutputBaseFilename=双色球选号工具-Setup
PrivilegesRequired=lowest
UninstallDisplayIcon={app}\双色球选号工具.exe
ArchitecturesInstallIn64BitMode=x64compatible
Compression=lzma
SolidCompression=yes
WizardStyle=modern

[Languages]
Name: "english"; MessagesFile: "compiler:Default.isl"

[Tasks]
Name: "desktopicon"; Description: "创建桌面快捷方式"; GroupDescription: "附加快捷方式："; Flags: unchecked

[Files]
Source: "{#SourceDir}\dist\双色球选号工具.exe"; DestDir: "{app}"; Flags: ignoreversion

[Icons]
Name: "{group}\双色球选号工具"; Filename: "{app}\双色球选号工具.exe"
Name: "{autodesktop}\双色球选号工具"; Filename: "{app}\双色球选号工具.exe"; Tasks: desktopicon
