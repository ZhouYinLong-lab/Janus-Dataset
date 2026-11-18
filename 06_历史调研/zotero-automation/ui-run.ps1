param([ValidateSet('inspect','menu','developer','dialog','execute')][string]$Action='inspect',[string]$ScriptPath)
$ErrorActionPreference='Stop'
Add-Type -AssemblyName UIAutomationClient
Add-Type -AssemblyName UIAutomationTypes
Add-Type -AssemblyName System.Windows.Forms
Add-Type @'
using System; using System.Runtime.InteropServices;
public static class JanusUi {
 [DllImport("user32.dll")] public static extern bool SetForegroundWindow(IntPtr h);
 [DllImport("user32.dll")] public static extern bool ShowWindow(IntPtr h,int n);
 [DllImport("user32.dll")] public static extern bool SetCursorPos(int x,int y);
 [DllImport("user32.dll")] public static extern void mouse_event(uint f,uint x,uint y,uint d,UIntPtr extra);
}
'@
$proc=Get-Process zotero | Where-Object MainWindowHandle -ne 0 | Select-Object -First 1
if (-not $proc) { throw 'No Zotero window' }
[JanusUi]::ShowWindow($proc.MainWindowHandle,9) | Out-Null
[JanusUi]::SetForegroundWindow($proc.MainWindowHandle) | Out-Null
Start-Sleep -Milliseconds 400
$root=[System.Windows.Automation.AutomationElement]::RootElement
$win=[System.Windows.Automation.AutomationElement]::FromHandle($proc.MainWindowHandle)
if ($Action -eq 'menu') { [System.Windows.Forms.SendKeys]::SendWait('%t'); Start-Sleep -Milliseconds 250 }
if ($Action -eq 'developer' -or $Action -eq 'dialog') {
 $targetName=if($Action -eq 'developer'){'开发者'}else{'Run JavaScript'}
 $els=$win.FindAll([System.Windows.Automation.TreeScope]::Descendants,[System.Windows.Automation.Condition]::TrueCondition)
 $target=$els | Where-Object { $_.Current.Name -like "$targetName*" } | Select-Object -First 1
 if(-not $target){throw "Menu not found: $targetName"}
 try{$target.GetCurrentPattern([System.Windows.Automation.ExpandCollapsePattern]::Pattern).Expand()}catch{$target.GetCurrentPattern([System.Windows.Automation.InvokePattern]::Pattern).Invoke()}
 Start-Sleep -Milliseconds 350
}
if ($Action -eq 'execute') {
 if(-not(Test-Path -LiteralPath $ScriptPath)){throw 'Script file missing'}
 $dialogs=$root.FindAll([System.Windows.Automation.TreeScope]::Children,[System.Windows.Automation.Condition]::TrueCondition)
 $dialog=$dialogs | Where-Object { $_.Current.Name -match 'JavaScript' } | Select-Object -First 1
 if(-not $dialog){throw 'Run JavaScript dialog missing'}
 $edits=$dialog.FindAll([System.Windows.Automation.TreeScope]::Descendants,(New-Object System.Windows.Automation.PropertyCondition([System.Windows.Automation.AutomationElement]::ControlTypeProperty,[System.Windows.Automation.ControlType]::Edit)))
 $input=$edits | Where-Object {$_.Current.Name -eq ''} | Select-Object -First 1
 if(-not $input){throw 'Script editor missing'}
 $savedClipboard=[System.Windows.Forms.Clipboard]::GetDataObject()
 [System.Windows.Forms.Clipboard]::SetText((Get-Content -LiteralPath $ScriptPath -Raw))
 [JanusUi]::SetForegroundWindow([IntPtr]$dialog.Current.NativeWindowHandle) | Out-Null
 $editor=$dialog.FindAll([System.Windows.Automation.TreeScope]::Descendants,[System.Windows.Automation.Condition]::TrueCondition) | Where-Object {$_.Current.Name -eq '代码：' -and $_.Current.BoundingRectangle.Width -gt 400} | Select-Object -First 1
 if(-not $editor){throw 'Code editor region missing'}
 $rect=$editor.Current.BoundingRectangle
 [JanusUi]::SetCursorPos([int]($rect.Left+80),[int]($rect.Top+45)) | Out-Null
 [JanusUi]::mouse_event(2,0,0,0,[UIntPtr]::Zero)
 [JanusUi]::mouse_event(4,0,0,0,[UIntPtr]::Zero)
 [System.Windows.Forms.SendKeys]::SendWait('^a')
 [System.Windows.Forms.SendKeys]::SendWait('^v')
 Start-Sleep -Milliseconds 400
 try { if($savedClipboard){[System.Windows.Forms.Clipboard]::SetDataObject($savedClipboard,$true)}else{[System.Windows.Forms.Clipboard]::Clear()} } catch { Write-Output 'Clipboard restoration unavailable' }
 $buttons=$dialog.FindAll([System.Windows.Automation.TreeScope]::Descendants,(New-Object System.Windows.Automation.PropertyCondition([System.Windows.Automation.AutomationElement]::ControlTypeProperty,[System.Windows.Automation.ControlType]::Button)))
 $run=$buttons | Where-Object {$_.Current.Name -match '^(运行|执行|Run)'} | Select-Object -First 1
 if(-not $run){throw 'Run button missing'}
 $run.GetCurrentPattern([System.Windows.Automation.InvokePattern]::Pattern).Invoke()
 Write-Output 'Executed one prepared Zotero batch'
 exit
}
$els=$win.FindAll([System.Windows.Automation.TreeScope]::Descendants,[System.Windows.Automation.Condition]::TrueCondition)
$els | Where-Object {$_.Current.ControlType.ProgrammaticName -match 'MenuItem|Edit|Button|CheckBox|Window'} | ForEach-Object { "$($_.Current.ControlType.ProgrammaticName) $($_.Current.Name)" } | Select-Object -First 80
