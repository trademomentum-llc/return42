; Inno Setup script for Return42 ClinicLink Windows installer.
; Build on Windows with Inno Setup Compiler (isc.exe) or via GitHub Actions.

#define MyAppName "Return42 ClinicLink"
#define MyAppVersion "1.0.0"
#define MyAppPublisher "TradeMomentum LLC"
#define MyAppURL "https://github.com/trademomentum-llc/return42"

[Setup]
AppId={{E3D8C9A1-7B6E-4F2A-9C5D-1E4A7B8C3D2F}
AppName={#MyAppName}
AppVersion={#MyAppVersion}
AppPublisher={#MyAppPublisher}
AppPublisherURL={#MyAppURL}
AppSupportURL={#MyAppURL}
AppUpdatesURL={#MyAppURL}
DefaultDirName={autopf}\Return42
DisableProgramGroupPage=yes
OutputDir=..\build
OutputBaseFilename=Return42-ClinicLink-1.0.0-Windows-x86_64
Compression=lzma
SolidCompression=yes
WizardStyle=modern
PrivilegesRequired=admin

[Languages]
Name: "english"; MessagesFile: "compiler:Default.isl"

[Files]
Source: "..\build\installer\bin\r42-cliniclink.exe"; DestDir: "{app}"; Flags: ignoreversion
Source: "..\build\installer\bin\r42-observe.exe"; DestDir: "{app}"; Flags: ignoreversion
Source: "..\cliniclink-desktop\src-tauri\target\release\cliniclink-desktop.exe"; DestDir: "{app}"; DestName: "ClinicLink Desktop.exe"; Flags: ignoreversion

[Icons]
Name: "{autoprograms}\Return42 ClinicLink"; Filename: "{app}\r42-cliniclink.exe"; Parameters: "--help"
Name: "{autoprograms}\Return42 Observability"; Filename: "{app}\r42-observe.exe"; Parameters: "--help"
Name: "{autoprograms}\ClinicLink Desktop"; Filename: "{app}\ClinicLink Desktop.exe"

[Registry]
Root: HKLM; Subkey: "SYSTEM\CurrentControlSet\Control\Session Manager\Environment"; ValueType: expandsz; ValueName: "Path"; ValueData: "{olddata};{app}"; Check: NeedsAddPath('{app}')

[Code]
function NeedsAddPath(Param: string): boolean;
var
  OrigPath: string;
begin
  if not RegQueryStringValue(HKLM, 'SYSTEM\CurrentControlSet\Control\Session Manager\Environment', 'Path', OrigPath) then
  begin
    Result := True;
    exit;
  end;
  Result := Pos(';' + Param + ';', ';' + OrigPath + ';') = 0;
end;
