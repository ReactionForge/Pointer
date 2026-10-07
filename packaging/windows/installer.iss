#ifndef AppVersion
  #define AppVersion "1.3.0-beta.5"
#endif

[Setup]
AppId={{B1F1B270-CA18-46B8-9951-437620DA32F8}
AppName=Pointer
AppVersion={#AppVersion}
AppPublisher=ReactionForge
AppPublisherURL=https://github.com/ReactionForge/Pointer
DefaultDirName={localappdata}\Pointer\app
DefaultGroupName=Pointer
PrivilegesRequired=lowest
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible
MinVersion=10.0
DisableProgramGroupPage=yes
DisableDirPage=no
UsePreviousAppDir=yes
OutputDir=..\..\dist
OutputBaseFilename=Pointer-v{#AppVersion}-setup-x64
SetupIconFile=pointer.ico
UninstallDisplayIcon={app}\pointer.ico
Compression=lzma2/ultra64
SolidCompression=yes
WizardStyle=modern
CloseApplications=no
RestartApplications=no
Uninstallable=yes
CreateAppDir=yes

[Languages]
Name: "english"; MessagesFile: "compiler:Default.isl"

[Tasks]
Name: "desktopicon"; Description: "Create a desktop shortcut"; Flags: unchecked

[Files]
Source: "..\..\dist\Pointer\*"; DestDir: "{tmp}\Pointer-payload"; Flags: ignoreversion recursesubdirs createallsubdirs deleteafterinstall

[Icons]
Name: "{group}\Pointer"; Filename: "{app}\Pointer.exe"; IconFilename: "{app}\pointer.ico"; IconIndex: 0
Name: "{group}\Uninstall Pointer"; Filename: "{uninstallexe}"; IconFilename: "{app}\pointer.ico"; IconIndex: 0
Name: "{autodesktop}\Pointer"; Filename: "{app}\Pointer.exe"; IconFilename: "{app}\pointer.ico"; IconIndex: 0; Tasks: desktopicon

[Run]
Filename: "{app}\Pointer.exe"; Description: "Open Pointer settings"; Flags: nowait postinstall skipifsilent

[Code]
var PayloadDeployed: Boolean;

procedure NotifyChangedIcon(EventID: LONG; Flags: UINT; Item1: String; Item2: LONG_PTR);
  external 'SHChangeNotify@shell32.dll stdcall setuponly';

procedure RefreshPointerIcons;
begin
  { Refresh only our installed icon and shortcuts after their targets exist. }
  NotifyChangedIcon($2000, $2005, ExpandConstant('{app}\pointer.ico'), 0);
  NotifyChangedIcon($2000, $2005, ExpandConstant('{group}\Pointer.lnk'), 0);
  NotifyChangedIcon($2000, $2005, ExpandConstant('{group}\Uninstall Pointer.lnk'), 0);
  if IsTaskSelected('desktopicon') then
    NotifyChangedIcon($2000, $2005, ExpandConstant('{autodesktop}\Pointer.lnk'), 0);
end;

function DataDirectory(): String;
begin
  Result := ExtractFileDir(ExpandConstant('{app}')) + '\data';
end;

function PathArguments(): String;
begin
  Result := ' --install-dir "' + ExpandConstant('{app}') + '" --data-dir "' + DataDirectory() + '"';
end;

procedure EnsurePayloadDeployed;
var ExitCode: Integer;
begin
  if PayloadDeployed then
    Exit;
  if not Exec(ExpandConstant('{tmp}\Pointer-payload\Pointer.exe'),
    '--install --quiet' + PathArguments(), '', SW_HIDE, ewWaitUntilTerminated, ExitCode) then
    RaiseException('Pointer installation could not start. Your settings are preserved.');
  if ExitCode <> 0 then
    RaiseException('Pointer installation failed. See the operation report in your Pointer data folder.');
  PayloadDeployed := True;
end;

procedure CurStepChanged(CurStep: TSetupStep);
begin
  if CurStep = ssPostInstall then
  begin
    EnsurePayloadDeployed;
    RefreshPointerIcons;
  end;
end;

function InitializeUninstall(): Boolean;
var ExitCode: Integer; Arguments: String;
begin
  Arguments := '--uninstall --quiet' + PathArguments();
  if not UninstallSilent then
    if MsgBox('Also remove custom Pointer preferences? The original cursor backup will be kept.', mbConfirmation, MB_YESNO) = IDYES then
      Arguments := Arguments + ' --purge-settings';
  Result := Exec(ExpandConstant('{app}\Pointer.exe'), Arguments, '', SW_HIDE, ewWaitUntilTerminated, ExitCode);
  if Result then Result := ExitCode = 0;
  if not Result then
    MsgBox('The original cursor could not be restored. Uninstallation has stopped and program files are preserved.', mbError, MB_OK);
end;

procedure CurUninstallStepChanged(CurUninstallStep: TUninstallStep);
var Lines: TArrayOfString; Index, Separator: Integer; Name, Digest, Filename: String;
begin
  if CurUninstallStep = usUninstall then
  begin
    if not LoadStringsFromFile(DataDirectory() + '\uninstall-owned-files.txt', Lines) then
      RaiseException('Missing verified cleanup list. Program files are preserved.');
    for Index := 0 to GetArrayLength(Lines)-1 do
    begin
      Separator := Pos('|', Lines[Index]);
      if Separator > 0 then
      begin
        Name := Copy(Lines[Index], 1, Separator-1);
        Digest := Copy(Lines[Index], Separator+1, MaxInt);
        if (Pos('..', Name) = 0) and (Pos(':', Name) = 0) and (Copy(Name,1,1) <> '\') and (Copy(Name,1,1) <> '/') then
        begin
          StringChangeEx(Name, '/', '\', True);
          Filename := ExpandConstant('{app}\') + Name;
          if FileExists(Filename) then
            if CompareText(GetSHA256OfFile(Filename), Digest) = 0 then
              if not DeleteFile(Filename) then
                RaiseException('A Pointer file is still in use. Close Pointer and retry uninstall.');
        end;
      end;
    end;
    DeleteFile(DataDirectory() + '\uninstall-owned-files.txt');
  end;
end;
